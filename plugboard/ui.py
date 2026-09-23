"""HTML for the local dashboard. One page, no build step, no CDN, no fonts fetched.

The layout is a left-to-right pipeline - brief, matches, approval queue, deals - because
that is the actual state machine, and the approval column is deliberately the loudest
thing on the screen: it is the only place a human decision is required and the only place
a message can move outward.
"""
from __future__ import annotations

import html

from . import tracking

CSS = """
:root{
  --ink:#0d0f12; --panel:#15181d; --line:#262b33; --text:#e7e9ee; --muted:#8b94a3;
  --accent:#ffd84d; --go:#4ade80; --stop:#f87171; --cool:#7dd3fc;
  --mono:ui-monospace,"DejaVu Sans Mono",Menlo,Consolas,monospace;
  --pad:18px;
}
*{box-sizing:border-box}
body{margin:0;background:
      radial-gradient(1100px 500px at 12% -10%, #1d2230 0%, transparent 60%), var(--ink);
     color:var(--text);font-family:var(--mono);font-size:13px;line-height:1.5;}
header{display:flex;align-items:baseline;gap:18px;padding:22px 26px 14px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:19px;letter-spacing:.14em;text-transform:uppercase}
h1 span{color:var(--accent)}
.sub{color:var(--muted);font-size:12px}
.badge{margin-left:auto;border:1px solid var(--line);padding:4px 10px;color:var(--muted)}
.badge b{color:var(--go)}
.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--line);
      border-bottom:1px solid var(--line)}
.col{background:var(--panel);padding:var(--pad);min-height:260px}
.col h2{margin:0 0 4px;font-size:11px;letter-spacing:.2em;color:var(--muted);text-transform:uppercase}
.col .n{font-size:30px;line-height:1;margin:2px 0 12px}
.col.gate{background:linear-gradient(180deg,#1c1a12 0%,var(--panel) 55%);border-top:2px solid var(--accent)}
.col.gate .n{color:var(--accent)}
.card{border:1px solid var(--line);padding:10px 11px;margin-bottom:9px;background:#11141a}
.card.top{border-left:3px solid var(--cool)}
.card .id{color:var(--muted);font-size:11px}
.row{display:flex;gap:8px;align-items:baseline}
.score{font-size:16px;color:var(--cool);min-width:52px}
.tier{border:1px solid var(--line);padding:0 5px;font-size:11px;color:var(--muted)}
.why{color:var(--muted);font-size:11.5px;margin-top:5px}
.why b{color:var(--text);font-weight:400}
.bar{height:3px;background:#20242c;margin-top:7px;position:relative}
.bar i{position:absolute;inset:0 auto 0 0;background:var(--cool)}
form{display:inline}
button{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
       border:1px solid var(--line);background:#1b1f26;color:var(--text);padding:6px 11px;cursor:pointer}
button.go{border-color:var(--go);color:var(--go)}
button.go:hover{background:var(--go);color:#07120b}
button.stop{border-color:var(--stop);color:var(--stop)}
button.stop:hover{background:var(--stop);color:#1a0808}
button:disabled{opacity:.35;cursor:not-allowed}
.actions{margin-top:9px;display:flex;gap:7px}
pre{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;color:var(--muted);font-size:11.5px;
    max-height:190px;overflow:auto;border-left:2px solid var(--line);padding-left:9px}
.state{font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.state.pending{color:var(--accent)}
.state.approved{color:var(--go)}
.state.sent{color:var(--cool)}
.state.rejected{color:var(--stop)}
.hint{color:var(--muted);font-size:11px;border:1px dashed var(--line);padding:9px;margin-top:10px}
.trail{padding:16px 26px 40px}
.trail h2{font-size:11px;letter-spacing:.2em;color:var(--muted);text-transform:uppercase;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:11.5px}
td{padding:4px 10px 4px 0;border-bottom:1px solid #1b1f26;color:var(--muted);vertical-align:top}
td.k{color:var(--text);white-space:nowrap}
.kpi{display:flex;gap:26px;flex-wrap:wrap;margin-top:8px}
.kpi div span{display:block;color:var(--muted);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase}
.kpi div b{font-size:17px;font-weight:400}
@media(max-width:1100px){.flow{grid-template-columns:1fr 1fr}}
@media(max-width:680px){.flow{grid-template-columns:1fr}}
"""


def e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _campaign_col(campaign) -> str:
    if not campaign:
        return ("<div class='col'><h2>1 - Brief</h2><div class='n'>0</div>"
                "<div class='hint'>No campaign yet. Run <b>plugboard brief &lt;file&gt; --id &lt;name&gt;</b>."
                "</div></div>")
    warn = "".join(f"<div class='hint'>! {e(w)}</div>" for w in campaign.warnings)
    return f"""<div class='col'>
      <h2>1 - Brief parsed</h2>
      <div class='n'>{e(campaign.campaign_id)}</div>
      <div class='card'>
        <div class='row'><b>{e(campaign.product)}</b></div>
        <div class='why'>goal <b>{e(campaign.goal)}</b> &middot; KPIs {e(', '.join(campaign.kpis))}</div>
        <div class='why'>topics <b>{e(', '.join(campaign.interests) or 'none')}</b></div>
        <div class='why'>audience {e('/'.join(campaign.languages) or 'any')} &middot;
             {e(campaign.geo or 'any geo')} &middot; {e(campaign.audience_age_band)}</div>
        <div class='why'>platforms {e(', '.join(campaign.platforms) or 'any')}</div>
        <div class='why'>budget <b>${campaign.budget_total_usd:,}</b> total,
             ${campaign.budget_per_creator_usd:,}/creator, target CPM ${campaign.target_cpm_usd:.2f}</div>
        <div class='why'>deliverables {e(', '.join(campaign.deliverables) or 'unspecified')}</div>
      </div>{warn}
    </div>"""


def _match_col(matches, creators) -> str:
    labels = {c.creator_id: c.display_label for c in creators}
    cards = []
    for i, match in enumerate(matches[:5]):
        top = sorted(match.lines, key=lambda l: -l.contribution)[:2]
        why = "<br>".join(f"<b>{e(l.name)}</b> {l.contribution:.3f} &middot; {e(l.reason)}" for l in top)
        cards.append(f"""<div class='card {"top" if i == 0 else ""}'>
            <div class='row'><span class='score'>{match.score:.3f}</span>
              <span class='tier'>tier {e(match.tier)}</span>
              <span class='id'>{e(match.creator_id)}</span></div>
            <div class='why'><b>{e(labels.get(match.creator_id, ''))}</b></div>
            <div class='bar'><i style='width:{min(match.score, 1.0) * 100:.0f}%'></i></div>
            <div class='why'>{why}</div>
            <div class='why'>offer <b>${match.suggested_offer_usd:,}</b> &middot;
                 est. {match.projected_views_low:,}-{match.projected_views_high:,} views</div>
          </div>""")
    body = "".join(cards) or "<div class='hint'>No matches yet. Run <b>plugboard match</b>.</div>"
    return f"<div class='col'><h2>2 - Matched &amp; explained</h2><div class='n'>{len(matches)}</div>{body}</div>"


def _queue_col(drafts, token) -> str:
    cards = []
    for row in drafts[:6]:
        state = e(row.get("status", ""))
        can_act = state == "pending"
        can_send = state == "approved"
        approved = (f"<div class='why'>approved by <b>{e(row.get('approved_by'))}</b> "
                    f"{e(row.get('approved_at'))}</div>" if row.get("approved_by") else "")
        cards.append(f"""<div class='card'>
            <div class='row'><span class='state {state}'>{state}</span>
              <span class='id'>{e(row.get('draft_id'))}</span></div>
            <div class='why'><b>{e(row.get('subject'))}</b></div>
            {approved}
            <div class='why'>bound to hash {e(str(row.get('body_hash', ''))[:24])}...</div>
            <pre>{e(row.get('body', ''))}</pre>
            <div class='actions'>
              <form method='post' action='/approve'>
                <input type='hidden' name='token' value='{e(token)}'>
                <input type='hidden' name='draft_id' value='{e(row.get('draft_id'))}'>
                <button class='go' {'' if can_act else 'disabled'}>Approve</button></form>
              <form method='post' action='/reject'>
                <input type='hidden' name='token' value='{e(token)}'>
                <input type='hidden' name='draft_id' value='{e(row.get('draft_id'))}'>
                <button class='stop' {'' if can_act else 'disabled'}>Reject</button></form>
              <form method='post' action='/send'>
                <input type='hidden' name='token' value='{e(token)}'>
                <input type='hidden' name='draft_id' value='{e(row.get('draft_id'))}'>
                <button {'' if can_send else 'disabled'}>Send</button></form>
            </div>
          </div>""")
    body = "".join(cards) or "<div class='hint'>Queue is empty. Run <b>plugboard draft</b>.</div>"
    pending = sum(1 for d in drafts if d.get("status") == "pending")
    return f"""<div class='col gate'><h2>3 - Human approval gate</h2><div class='n'>{pending}</div>
      <div class='hint'>Nothing leaves this machine without a click here. Approval signs the exact
      text; editing it afterwards revokes the signature.</div>{body}</div>"""


def _deal_col(deals, summary, due) -> str:
    cards = []
    for deal in deals[:4]:
        done = sum(1 for d in deal.deliverables if d.status in ("delivered", "live"))
        cpm = f"${deal.actual_cpm():.2f}" if deal.actual_cpm() else "-"
        cards.append(f"""<div class='card'>
            <div class='row'><span class='state {e(deal.status)}'>{e(deal.status)}</span>
              <span class='id'>{e(deal.deal_id)}</span></div>
            <div class='why'>fee <b>${deal.agreed_fee_usd:,}</b> &middot;
              deliverables {done}/{len(deal.deliverables)} &middot;
              views <b>{deal.total_views():,}</b> &middot; actual CPM {cpm}</div>
          </div>""")
    overdue = "".join(
        f"<div class='hint'>{'OVERDUE' if r['overdue'] else 'due in ' + str(r['days_left']) + 'd'}: "
        f"{e(r['description'])} ({e(r['due_on'])}) - {e(r['creator_id'])}</div>" for r in due[:3])
    body = "".join(cards) or "<div class='hint'>No deals yet.</div>"
    return f"""<div class='col'><h2>4 - Deals &amp; results</h2><div class='n'>{len(deals)}</div>
      <div class='kpi'>
        <div><span>views</span><b>{summary['views']:,}</b></div>
        <div><span>spend</span><b>${summary['committed_usd']:,}</b></div>
        <div><span>blended CPM</span><b>${summary['blended_cpm_usd']:.2f}</b></div>
        <div><span>delivery</span><b>{summary['delivery_rate'] * 100:.0f}%</b></div>
      </div>{body}{overdue}</div>"""


def _trail(events) -> str:
    rows = "".join(
        f"<tr><td class='k'>{e(ev.get('at'))}</td><td class='k'>{e(ev.get('kind'))}</td>"
        f"<td>{e(ev.get('ref'))}</td>"
        f"<td>{e(' '.join(f'{k}={v}' for k, v in (ev.get('detail') or {}).items()))}</td></tr>"
        for ev in reversed(events[-14:]))
    return (f"<div class='trail'><h2>Audit trail - every state change, append-only</h2>"
            f"<table>{rows or '<tr><td>nothing yet</td></tr>'}</table></div>")


def page(pb, campaign, matches, drafts, deals, token: str) -> str:
    summary = (tracking.campaign_summary(pb.store, campaign.campaign_id) if campaign
               else {"views": 0, "committed_usd": 0, "blended_cpm_usd": 0.0, "delivery_rate": 0.0})
    due = tracking.due_soon(pb.store, 7)
    mode = "LIVE SEND" if pb.settings.sending_is_live else "DRY RUN"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Plugboard</title><style>{CSS}</style></head><body>
<header>
  <h1>Plug<span>board</span></h1>
  <div class='sub'>brief &rarr; match &rarr; approve &rarr; track</div>
  <div class='badge'>send mode <b>{e(mode)}</b> &middot; solana {e(pb.settings.solana_cluster)}</div>
</header>
<div class='flow'>
  {_campaign_col(campaign)}
  {_match_col(matches, pb.creators)}
  {_queue_col(drafts, token)}
  {_deal_col(deals, summary, due)}
</div>
{_trail(pb.store.events(0))}
</body></html>"""
