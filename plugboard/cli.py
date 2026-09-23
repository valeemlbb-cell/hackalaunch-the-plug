"""`plugboard <command>` - the whole loop from a terminal.

    plugboard brief data/briefs/sample_brief.txt --id kilat
    plugboard match --campaign kilat --limit 5
    plugboard draft --campaign kilat --limit 3
    plugboard queue
    plugboard approve d-kilat-c014 --by henggar
    plugboard send d-kilat-c014
    plugboard reply d-kilat-c014 --text "interested, my rate is 400"
    plugboard deal open --campaign kilat --creator c014 --fee 400
    plugboard deal deliverable deal-kilat-c014 --desc "1 x TikTok" --due 2026-10-03
    plugboard result deal-kilat-c014 --deliverable deal-kilat-c014-d1 --platform tiktok --url URL --views 41000
    plugboard due --days 5
    plugboard report --campaign kilat
    plugboard receipt anchor --deal deal-kilat-c014
    plugboard serve --port 8799
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import approval, outreach, receipts, tracking
from .app import Plugboard
from .brief import parse_brief
from .models import as_dict
from .senders import build_sender
from .store import today

RULE = "-" * 78


def _out(text: str = "") -> None:
    print(text, flush=True)


def _head(title: str) -> None:
    _out()
    _out(f"== {title}")
    _out(RULE)


# ------------------------------------------------------------------ commands
def cmd_brief(pb: Plugboard, args) -> int:
    raw = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8-sig").read()
    campaign = parse_brief(raw, args.id, llm=pb.llm)
    pb.save_campaign(campaign)
    _head(f"BRIEF -> CAMPAIGN  {campaign.campaign_id}")
    _out(f"  product      {campaign.product}")
    _out(f"  goal         {campaign.goal}      KPIs: {', '.join(campaign.kpis)}")
    _out(f"  audience     {'/'.join(campaign.languages) or 'any'}  geo {campaign.geo or 'any'}  "
         f"age {campaign.audience_age_band}")
    _out(f"  topics       {', '.join(campaign.interests) or '(none found)'}")
    _out(f"  platforms    {', '.join(campaign.platforms) or 'any'}")
    _out(f"  budget       ${campaign.budget_total_usd:,} total, ${campaign.budget_per_creator_usd:,}/creator, "
         f"target CPM ${campaign.target_cpm_usd:.2f}")
    _out(f"  deliverables {', '.join(campaign.deliverables) or '(not specified)'}")
    _out(f"  window       {campaign.starts_on or '?'} -> {campaign.ends_on or '?'}")
    for warning in campaign.warnings:
        _out(f"  ! {warning}")
    return 0


def cmd_match(pb: Plugboard, args) -> int:
    campaign = pb.campaign(args.campaign)
    picks = pb.run_matching(campaign, limit=args.limit, diversify=not args.no_diversity)
    everything = pb.stored_matches(campaign.campaign_id)
    excluded = [m for m in everything if m.excluded]
    _head(f"MATCH  {campaign.campaign_id}  ({len(everything)} creators scored, "
          f"{len(excluded)} filtered out, {len(picks)} selected)")
    for rank, match in enumerate(picks, 1):
        creator = pb.creator(match.creator_id)
        label = creator.display_label if creator else match.creator_id
        _out(f"{rank}. [{match.tier}] {match.score:.3f}  {match.creator_id}  {label}")
        for line in sorted(match.lines, key=lambda l: -l.contribution):
            _out(f"       {line.name:<19} {line.contribution:.3f}   {line.reason}")
        if match.evidence:
            _out(f"       evidence            {match.evidence[0]}")
        _out(f"       offer               ${match.suggested_offer_usd:,}  "
             f"projected {match.projected_views_low:,}-{match.projected_views_high:,} views (estimate)")
        for risk in match.risks:
            _out(f"       risk                {risk}")
        _out()
    if excluded and args.show_excluded:
        _out("Filtered out:")
        for match in excluded:
            _out(f"   x {match.creator_id}  {match.exclusion_reason}")
    return 0


def cmd_draft(pb: Plugboard, args) -> int:
    campaign = pb.campaign(args.campaign)
    matches = [m for m in pb.stored_matches(campaign.campaign_id) if not m.excluded]
    if not matches:
        _out("no matches stored yet - run: plugboard match --campaign " + campaign.campaign_id)
        return 1
    wanted = [m for m in matches if not args.creator or m.creator_id in args.creator][:args.limit]
    drafts, skipped = [], []
    for match in wanted:
        creator = pb.creator(match.creator_id)
        try:
            drafts.append(outreach.compose(campaign, creator, match, signature=pb.signature(), llm=pb.llm))
        except outreach.OutreachError as exc:
            skipped.append(str(exc))
    staged = approval.queue(pb.store, drafts)
    _head(f"DRAFT  {len(staged)} message(s) staged for human approval")
    for draft in staged:
        _out(f"  {draft.draft_id}   {draft.creator_id}   via {draft.channel}   [{draft.language}]   "
             f"status={draft.status}")
    for reason in skipped:
        _out(f"  ! skipped: {reason}")
    if staged:
        _out()
        _out("Nothing has been sent. Review with `plugboard show <draft_id>`, then "
             "`plugboard approve <draft_id> --by <your name>`.")
    return 0


def cmd_show(pb: Plugboard, args) -> int:
    row = pb.store.find("drafts", "draft_id", args.draft_id)
    if not row:
        _out(f"no draft {args.draft_id}")
        return 1
    _head(f"DRAFT {row['draft_id']}   status={row['status']}")
    _out(f"  to       {row['creator_id']} via {row['channel']}")
    _out(f"  subject  {row['subject']}")
    _out(f"  hash     {row.get('body_hash','')[:16]}...")
    if row.get("approved_by"):
        _out(f"  approved {row['approved_by']} at {row['approved_at']}")
    _out(RULE)
    _out(row["body"])
    _out(RULE)
    return 0


def cmd_queue(pb: Plugboard, args) -> int:
    rows = pb.drafts(status=args.status)
    _head(f"APPROVAL QUEUE  ({len(rows)} {args.status or 'total'})")
    if not rows:
        _out("  (empty)")
    for row in rows:
        _out(f"  [{row['status']:<8}] {row['draft_id']:<28} {row['creator_id']:<8} "
             f"{row['subject'][:44]}")
    _out()
    _out("HUMAN GATE: a message is sent only after `plugboard approve <id> --by <name>`.")
    return 0


def cmd_approve(pb: Plugboard, args) -> int:
    operator = args.by or pb.settings.operator
    draft = approval.approve(pb.store, pb.secret, args.draft_id, operator)
    _head(f"APPROVED  {draft.draft_id}")
    _out(f"  by        {draft.approved_by} at {draft.approved_at}")
    _out(f"  bound to  {draft.body_hash[:32]}...")
    _out(f"  token     {draft.approval_token[:32]}...")
    _out("  Editing the text after this point revokes the approval automatically.")
    return 0


def cmd_reject(pb: Plugboard, args) -> int:
    draft = approval.reject(pb.store, args.draft_id, args.by or pb.settings.operator, args.reason)
    _out(f"rejected {draft.draft_id}: {draft.rejected_reason}")
    return 0


def cmd_edit(pb: Plugboard, args) -> int:
    body = sys.stdin.read() if args.body == "-" else args.body
    draft = approval.edit(pb.store, args.draft_id, subject=args.subject, body=body)
    _out(f"{draft.draft_id} edited -> status={draft.status} (approval revoked, needs re-approval)")
    return 0


def cmd_send(pb: Plugboard, args) -> int:
    row = pb.store.find("drafts", "draft_id", args.draft_id) or {}
    sender = build_sender(pb.settings, pb.contact_for(row.get("creator_id", "")))
    draft = approval.send(pb.store, pb.secret, args.draft_id, sender)
    _head(f"SENT  {draft.draft_id}  ({sender.mode})")
    _out(f"  to    {draft.creator_id} via {draft.channel}")
    _out(f"  ref   {draft.send_ref}")
    if sender.mode == "dry_run":
        _out("  dry run: the message was written to the outbox, not delivered. "
             "Set PLUGBOARD_SEND_MODE=live plus SMTP_* to deliver for real.")
    return 0


def cmd_reply(pb: Plugboard, args) -> int:
    row = pb.store.find("drafts", "draft_id", args.draft_id)
    if not row:
        _out(f"no draft {args.draft_id}")
        return 1
    verdict = outreach.classify_reply(args.text, llm=pb.llm)
    pb.store.log("reply.received", args.draft_id, creator=row["creator_id"],
                 intent=verdict["intent"], by=verdict["by"])
    _head(f"REPLY on {args.draft_id}")
    _out(f"  from      {row['creator_id']}")
    _out(f"  intent    {verdict['intent']}  (confidence {verdict['confidence']:.2f}, by {verdict['by']})")
    _out(f"  next      {verdict['next_action']}")
    if verdict["intent"] == "unsubscribe":
        pb.store.block(row["creator_id"], "replied opt-out")
        _out(f"  {row['creator_id']} added to the blocklist permanently. No further drafts will be built.")
    return 0


def cmd_deal(pb: Plugboard, args) -> int:
    if args.deal_cmd == "open":
        deal = tracking.open_deal(pb.store, args.campaign, args.creator, args.fee)
        _out(f"deal {deal.deal_id} opened  status={deal.status}  fee ${deal.agreed_fee_usd:,}")
    elif args.deal_cmd == "status":
        deal = tracking.set_status(pb.store, args.deal_id, args.status)
        _out(f"deal {deal.deal_id} -> {deal.status}")
    elif args.deal_cmd == "deliverable":
        deal = tracking.add_deliverable(pb.store, args.deal_id, args.desc, args.due)
        item = deal.deliverables[-1]
        _out(f"{item.deliverable_id}  {item.description}  due {item.due_on}")
    elif args.deal_cmd == "mark":
        tracking.mark_deliverable(pb.store, args.deal_id, args.deliverable, args.state, args.proof)
        _out(f"{args.deliverable} -> {args.state}")
    return 0


def cmd_result(pb: Plugboard, args) -> int:
    deal = tracking.record_result(
        pb.store, args.deal_id, args.deliverable, args.platform, args.url,
        views=args.views, likes=args.likes, comments=args.comments, shares=args.shares,
        clicks=args.clicks, conversions=args.conversions, source=args.source)
    _head(f"RESULT recorded on {deal.deal_id}")
    _out(f"  {args.platform}  {args.url}")
    _out(f"  views {args.views:,}   total on this deal {deal.total_views():,}")
    if deal.actual_cpm():
        _out(f"  actual CPM ${deal.actual_cpm():.2f} against a ${deal.agreed_fee_usd:,} fee")
    return 0


def cmd_due(pb: Plugboard, args) -> int:
    rows = tracking.due_soon(pb.store, args.days, args.as_of)
    _head(f"DELIVERABLES DUE within {args.days} day(s) of {args.as_of or today()}")
    if not rows:
        _out("  nothing due")
    for row in rows:
        flag = "OVERDUE" if row["overdue"] else f"in {row['days_left']}d"
        _out(f"  [{flag:>8}] {row['due_on']}  {row['creator_id']:<8} {row['description'][:38]:<38} "
             f"{row['deliverable_id']}")
    return 0


def cmd_report(pb: Plugboard, args) -> int:
    summary = tracking.campaign_summary(pb.store, args.campaign)
    _head(f"CAMPAIGN REPORT  {args.campaign}")
    _out(f"  deals              {summary['deals']} ({summary['deals_live']} live)")
    _out(f"  committed spend    ${summary['committed_usd']:,}")
    _out(f"  views              {summary['views']:,}")
    _out(f"  clicks             {summary['clicks']:,}     conversions {summary['conversions']:,}")
    _out(f"  blended CPM        ${summary['blended_cpm_usd']:.2f}")
    if summary["cost_per_conversion_usd"]:
        _out(f"  cost / conversion  ${summary['cost_per_conversion_usd']:.2f}")
    _out(f"  deliverables       {summary['deliverables_done']}/{summary['deliverables_total']} done, "
         f"{summary['deliverables_missed']} missed  (rate {summary['delivery_rate'] * 100:.0f}%)")
    _out("  Every view figure above traces to a post URL recorded with `plugboard result`.")
    if args.json:
        _out(json.dumps(summary, indent=2))
    return 0


def cmd_receipt(pb: Plugboard, args) -> int:
    deal = tracking.load_deal(pb.store, args.deal)
    if args.receipt_cmd == "hash":
        _out(receipts.terms_hash(deal))
        return 0
    if args.receipt_cmd == "verify":
        row = pb.store.find("receipts", "deal_id", args.deal) or {}
        ok = receipts.verify_hash(deal, row.get("hash", ""))
        _head(f"RECEIPT VERIFY  {args.deal}")
        _out(f"  stored hash   {row.get('hash','(none)')}")
        _out(f"  recomputed    {receipts.terms_hash(deal)}")
        _out(f"  match         {'YES - terms are unchanged' if ok else 'NO - the terms changed since anchoring'}")
        if row.get("signature"):
            _out(f"  signature     {row['signature']}")
        return 0 if ok else 2
    outcome = receipts.anchor_deal(deal, pb.settings)
    pb.store.upsert("receipts", "deal_id", receipts.receipt_record(deal, outcome))
    pb.store.log("receipt.anchor", args.deal, anchored=outcome["anchored"],
                 cluster=outcome["cluster"], signature=outcome.get("signature", ""))
    _head(f"RECEIPT  {args.deal}")
    _out(f"  terms hash   {outcome['hash']}")
    _out(f"  cluster      {outcome['cluster']}")
    if outcome["anchored"]:
        _out(f"  signature    {outcome['signature']}")
        _out(f"  explorer     {outcome['explorer']}")
    else:
        _out(f"  not anchored: {outcome['reason']}")
        _out("  The hash is stored locally and stays verifiable; anchoring is optional.")
    return 0


def cmd_events(pb: Plugboard, args) -> int:
    rows = pb.store.events(args.limit)
    _head(f"AUDIT TRAIL  (last {len(rows)})")
    for row in rows:
        detail = " ".join(f"{k}={v}" for k, v in (row.get("detail") or {}).items())
        _out(f"  {row['at']}  {row['kind']:<20} {row['ref']:<28} {detail[:60]}")
    return 0


def cmd_creators(pb: Plugboard, args) -> int:
    _head(f"CREATOR INDEX  {pb.catalog_path}  ({len(pb.creators)} records)")
    for creator in pb.creators:
        top = creator.best_platform()
        reach = f"{top.platform} {top.median_views:,} med. views" if top else "no platform data"
        _out(f"  {creator.creator_id:<8} {creator.display_label[:42]:<42} {reach}")
    return 0


def cmd_serve(pb: Plugboard, args) -> int:
    from .web import serve
    serve(pb, host=args.host, port=args.port)
    return 0


# -------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plugboard", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", default="", help="state directory (default ./workspace)")
    parser.add_argument("--catalog", default="", help="creator index JSON (default data/creators.seed.json)")
    parser.add_argument("--no-llm", action="store_true", help="never call a model, even if one is configured")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("brief", help="parse a founder brief into a campaign")
    p.add_argument("path"); p.add_argument("--id", required=True); p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("match", help="rank creators against a campaign, with reasons")
    p.add_argument("--campaign", required=True); p.add_argument("--limit", type=int, default=5)
    p.add_argument("--no-diversity", action="store_true")
    p.add_argument("--show-excluded", action="store_true"); p.set_defaults(fn=cmd_match)

    p = sub.add_parser("draft", help="write outreach drafts and stage them for approval")
    p.add_argument("--campaign", required=True); p.add_argument("--limit", type=int, default=3)
    p.add_argument("--creator", action="append", default=[]); p.set_defaults(fn=cmd_draft)

    p = sub.add_parser("show", help="print one draft in full")
    p.add_argument("draft_id"); p.set_defaults(fn=cmd_show)

    p = sub.add_parser("queue", help="list drafts waiting on a human")
    p.add_argument("--status", default=""); p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("approve", help="a human approves one exact message")
    p.add_argument("draft_id"); p.add_argument("--by", default=""); p.set_defaults(fn=cmd_approve)

    p = sub.add_parser("reject", help="reject a draft")
    p.add_argument("draft_id"); p.add_argument("--reason", default=""); p.add_argument("--by", default="")
    p.set_defaults(fn=cmd_reject)

    p = sub.add_parser("edit", help="edit a draft (revokes approval)")
    p.add_argument("draft_id"); p.add_argument("--subject", default=None)
    p.add_argument("--body", default=None); p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("send", help="send one approved draft")
    p.add_argument("draft_id"); p.set_defaults(fn=cmd_send)

    p = sub.add_parser("reply", help="record a creator's reply and classify the intent")
    p.add_argument("draft_id"); p.add_argument("--text", required=True); p.set_defaults(fn=cmd_reply)

    p = sub.add_parser("deal", help="deal lifecycle")
    ds = p.add_subparsers(dest="deal_cmd", required=True)
    d = ds.add_parser("open"); d.add_argument("--campaign", required=True)
    d.add_argument("--creator", required=True); d.add_argument("--fee", type=int, default=0)
    d = ds.add_parser("status"); d.add_argument("deal_id"); d.add_argument("--status", required=True)
    d = ds.add_parser("deliverable"); d.add_argument("deal_id")
    d.add_argument("--desc", required=True); d.add_argument("--due", required=True)
    d = ds.add_parser("mark"); d.add_argument("deal_id"); d.add_argument("--deliverable", required=True)
    d.add_argument("--state", required=True); d.add_argument("--proof", default="")
    p.set_defaults(fn=cmd_deal)

    p = sub.add_parser("result", help="record measured results for a deliverable")
    p.add_argument("deal_id"); p.add_argument("--deliverable", required=True)
    p.add_argument("--platform", required=True); p.add_argument("--url", required=True)
    for field in ("views", "likes", "comments", "shares", "clicks", "conversions"):
        p.add_argument(f"--{field}", type=int, default=0)
    p.add_argument("--source", default="manual"); p.set_defaults(fn=cmd_result)

    p = sub.add_parser("due", help="deliverables due or overdue")
    p.add_argument("--days", type=int, default=3); p.add_argument("--as-of", dest="as_of", default="")
    p.set_defaults(fn=cmd_due)

    p = sub.add_parser("report", help="campaign performance summary")
    p.add_argument("--campaign", required=True); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("receipt", help="hash / anchor / verify deal terms on Solana devnet")
    rs = p.add_subparsers(dest="receipt_cmd", required=True)
    for name in ("anchor", "verify", "hash"):
        r = rs.add_parser(name); r.add_argument("--deal", required=True)
    p.set_defaults(fn=cmd_receipt)

    p = sub.add_parser("events", help="audit trail")
    p.add_argument("--limit", type=int, default=25); p.set_defaults(fn=cmd_events)

    p = sub.add_parser("creators", help="show the loaded creator index")
    p.set_defaults(fn=cmd_creators)

    p = sub.add_parser("serve", help="local dashboard (127.0.0.1 only)")
    p.add_argument("--port", type=int, default=8799); p.add_argument("--host", default="127.0.0.1")
    p.set_defaults(fn=cmd_serve)
    return parser


def main(argv: list = None) -> int:
    args = build_parser().parse_args(argv)
    pb = Plugboard(workspace=args.workspace, catalog_path=args.catalog, use_llm=not args.no_llm)
    try:
        return args.fn(pb, args)
    except (approval.ApprovalError, tracking.TrackingError, outreach.OutreachError,
            KeyError, ValueError, FileNotFoundError) as exc:
        _out(f"refused: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
