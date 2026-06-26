#!/usr/bin/env python3
"""
LNH Client Portal Generator
────────────────────────────
Reads a JSON data file (extracted from Notion intake form)
and outputs a complete client portal HTML file.

Usage:
  python3 generate_portal.py data.json output.html

The JSON should have keys matching Notion field names.
See FIELD_MAP below for expected keys.

Created by Claude for Let Nicole Help · June 2026
"""

import json, sys, re, html as html_mod
from datetime import datetime, date

# ─── UTILITIES ────────────────────────────────────────────

def esc(s):
    """HTML-escape a string."""
    if not s: return ''
    return html_mod.escape(str(s))

def clean_name(s):
    """Strip ** bold markers and \\~ escapes from Notion workflow names."""
    if not s: return ''
    s = s.strip().strip('*').strip()
    s = s.replace('\\\\~', '~').replace('\\~', '~')
    return s

def parse_steps(raw):
    """Split a <br>-delimited numbered step list into clean items."""
    if not raw: return []
    raw = raw.strip().strip('*').strip()
    lines = re.split(r'<br\s*/?>', raw)
    steps = []
    for line in lines:
        line = line.strip().strip('*').strip()
        line = re.sub(r'^\d+[\-\.\)]\s*', '', line)  # strip "1- ", "2. ", etc.
        line = line.replace('\\\\~', '~').replace('\\~', '~')
        if line:
            steps.append(line)
    return steps

def format_date_display(iso_str):
    """Convert 2026-06-22 to June 22, 2026."""
    if not iso_str: return ''
    try:
        d = datetime.strptime(iso_str[:10], '%Y-%m-%d')
        return d.strftime('%B %d, %Y').replace(' 0', ' ')
    except: return iso_str

def format_month_year(iso_str):
    """Convert 2026-06-22 to June 2026."""
    if not iso_str: return ''
    try:
        d = datetime.strptime(iso_str[:10], '%Y-%m-%d')
        return d.strftime('%B %Y')
    except: return iso_str

def format_checkin_label(iso_str):
    """Convert 2026-12-22 to Dec '26."""
    if not iso_str: return ''
    try:
        d = datetime.strptime(iso_str[:10], '%Y-%m-%d')
        return d.strftime("%b '%y")
    except: return iso_str

def make_client_key(name):
    """Convert 'Breathe Images' to 'breathe_images'."""
    if not name: return 'client'
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

def parse_workflow_groups(raw):
    """Parse 'Label: 1, 2, 3\\nLabel: 4, 5' into [(label, [1,2,3]), ...]."""
    if not raw: return []
    groups = []
    for line in raw.strip().split('\n'):
        line = line.strip()
        if ':' not in line: continue
        label, nums = line.split(':', 1)
        wf_nums = [int(n.strip()) for n in nums.split(',') if n.strip().isdigit()]
        groups.append((label.strip(), wf_nums))
    return groups

def parse_booking_details(raw):
    """Parse 'Field: value\\nField: value' into [(field, value), ...]."""
    if not raw: return []
    pairs = []
    for line in raw.strip().split('\n'):
        line = line.strip()
        if ':' not in line: continue
        key, val = line.split(':', 1)
        pairs.append((key.strip(), val.strip()))
    return pairs

def parse_booking_services(raw):
    """Parse '===Service Name===\\nField: value\\n...' into [(name, [(f,v),...]), ...]."""
    if not raw: return []
    services = []
    current_name = None
    current_details = []
    for line in raw.strip().split('\n'):
        line = line.strip()
        m = re.match(r'^===\s*(.+?)\s*===$', line)
        if m:
            if current_name:
                services.append((current_name, current_details))
            current_name = m.group(1)
            current_details = []
        elif ':' in line and current_name:
            key, val = line.split(':', 1)
            current_details.append((key.strip(), val.strip()))
    if current_name:
        services.append((current_name, current_details))
    return services


def parse_team_members(d):
    """Parse Team Members from JSON data. Returns {name: {emoji, color}}."""
    raw = d.get('Team Members')
    if isinstance(raw, dict) and raw:
        return raw
    return {}


def hex_to_rgba(hex_color, alpha='0.12'):
    """Convert #9b59b6 to rgba(155,89,182,0.12)."""
    h = hex_color.lstrip('#')
    if len(h) != 6:
        return f'rgba(128,128,128,{alpha})'
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def parse_pipeline_automations(auto_text, pipelines, all_wf):
    """Parse pipeline automation text into structured phase data per pipeline.

    pipelines: [(name, phase_count, image_url), ...]
    Returns: [(name, phase_count, image_url, [phase_dict, ...]), ...]
    Each phase_dict: {name, entries: [trigger_text, ...], exits: [trigger_text, ...], wf_tags: [name, ...]}
    """
    items = parse_steps(auto_text) if auto_text else []
    phases_list = []

    for item in items:
        m = re.search(r'(lands in|moves to|removed from)\s+"([^"]+)"', item)
        if not m:
            continue
        action, phase_name = m.group(1), m.group(2)
        trigger = item[m.end():].strip().lstrip(',').strip()
        if not trigger:
            trigger = item[:m.start()].strip().rstrip(',').strip()

        if phases_list and phases_list[-1]['name'] == phase_name:
            p = phases_list[-1]
        else:
            p = {'name': phase_name, 'entries': [], 'exits': [], 'wf_tags': set()}
            phases_list.append(p)

        if action == 'removed from':
            p['exits'].append(trigger)
        else:
            p['entries'].append(trigger)

        for wn in all_wf:
            wf_clean = clean_name(all_wf[wn]['name'])
            if wf_clean.lower() in item.lower():
                p['wf_tags'].add(wf_clean)

    result = []
    idx = 0
    for pname, pcount, pimg in pipelines:
        count = int(pcount) if pcount else 0
        pipeline_phases = []
        for i in range(count):
            if idx < len(phases_list):
                pd = phases_list[idx]
                pd['wf_tags'] = sorted(pd['wf_tags'])
                pipeline_phases.append(pd)
                idx += 1
        result.append((pname, count, pimg, pipeline_phases))

    return result


def parse_tag_to_phase_map(pipeline_auto_text, workflow_auto_text=''):
    """Build a mapping from tag names to pipeline phase names from automation text.
    Also builds a step keyword → phase mapping from workflow automations."""
    tag_map = {}
    if not pipeline_auto_text:
        return tag_map
    items = parse_steps(pipeline_auto_text)
    for item in items:
        phase_match = re.search(r'(?:lands in|moves to)\s+"([^"]+)"', item)
        if not phase_match:
            continue
        tag_match = re.search(r'\btag:\s*([^)]+)\)', item)
        if tag_match:
            tag_map[tag_match.group(1).strip().lower()] = phase_match.group(1)
            continue
        tag_match2 = re.search(r'"([^"]+)"\s+tag\s+is\s+added', item)
        if tag_match2:
            tag_map[tag_match2.group(1).strip().lower()] = phase_match.group(1)
            continue
        tag_match3 = re.search(r'adds\s+"([^"]+)"\s+tag', item)
        if tag_match3:
            tag_map[tag_match3.group(1).strip().lower()] = phase_match.group(1)

    # Build step keyword → phase mapping from workflow automations
    # e.g. "Dump raw images to-do adds 'theatre press' tag" → tag maps to Press Cull
    step_map = []
    if workflow_auto_text:
        wf_items = parse_steps(workflow_auto_text)
        for item in wf_items:
            todo_match = re.search(r'^(.+?)\s+to-do\s+adds\s+"([^"]+)"\s+tag', item, re.IGNORECASE)
            if todo_match:
                keyword = todo_match.group(1).strip().lower()
                tag = todo_match.group(2).strip().lower()
                if tag in tag_map:
                    step_map.append((keyword, tag_map[tag]))
    if step_map:
        tag_map['__step_map__'] = step_map

    return tag_map


def classify_journey_step(step_text, team_members, tag_phase_map=None):
    """Classify a workflow step for the journey map."""
    text = step_text.strip()
    node = {
        'text': text, 'type': 'automated', 'member_name': '', 'member_emoji': '',
        'member_color': '', 'description': text, 'timing': '',
        'is_client_facing': False, 'is_auto_email': False, 'is_transition': False,
        'transition_target': '', 'pipeline_change': '',
    }

    paren_match = re.search(r'\(([^)]+)\)\s*$', text)
    paren = paren_match.group(1) if paren_match else ''
    base = text[:paren_match.start()].strip() if paren_match else text

    found_member = False
    for mname, minfo in team_members.items():
        emoji = minfo.get('emoji', '')
        if emoji and base.startswith(emoji):
            node.update(type='manual', member_name=mname, member_emoji=emoji,
                        member_color=minfo.get('color', '#888'),
                        description=base[len(emoji):].strip())
            found_member = True
            break

    if not found_member and paren:
        for mname, minfo in team_members.items():
            if mname.lower() in paren.lower():
                node.update(member_name=mname, member_emoji=minfo.get('emoji', ''),
                            member_color=minfo.get('color', '#888'))
                found_member = True
                break

    if paren:
        parts = [p.strip() for p in paren.split(';')]
        timing_parts = [p for p in parts
                        if not any(m.lower() in p.lower() for m in team_members)
                        and 'moves' not in p.lower()
                        and p.lower().strip() not in ('automatic', 'automated',
                            'automatic upon starting workflow')]
        node['timing'] = '; '.join(timing_parts)

    if base.startswith('Send email:') or base.startswith('Send invoice:'):
        node['type'] = 'email'
        node['is_client_facing'] = True
        if paren and ('automatic' in paren.lower() or 'automated' in paren.lower()):
            node['is_auto_email'] = True
    elif base.startswith('Create Workflow:'):
        node['type'] = 'transition'
        node['is_transition'] = True
        node['transition_target'] = clean_name(base.replace('Create Workflow:', '').strip())
    elif base.startswith('Add Tag:') or base.startswith('Add/Remove Tags:'):
        node['type'] = 'automated'
    elif 'archive' in base.lower():
        node['type'] = 'automated'
    elif base.startswith('Pause for'):
        node['type'] = 'client_action'
        node['is_client_facing'] = True

    if paren and ('automatic' in paren.lower() or 'automated' in paren.lower()):
        if node['type'] not in ('email', 'transition', 'client_action'):
            node['type'] = 'automated'

    if found_member and node['type'] == 'automated':
        if not (paren and ('automatic' in paren.lower() or 'automated' in paren.lower())):
            node['type'] = 'manual'

    pm = re.search(r'moves (?:client |.+?)?to [“”]([^””]+)[“”]', text, re.IGNORECASE)
    if pm:
        node['pipeline_change'] = pm.group(1)

    if not node['pipeline_change'] and tag_phase_map:
        # Check for +tag syntax in step text
        tag_matches = re.findall(r'\+([a-z][a-z0-9 ]+)', text.lower())
        for tag in tag_matches:
            tag_clean = tag.strip()
            if tag_clean in tag_phase_map:
                node['pipeline_change'] = tag_phase_map[tag_clean]
                break
        # Check for adds "tagname" tag pattern (use last match — later tags are typically more significant)
        if not node['pipeline_change']:
            adds_matches = re.findall(r'adds\s+"([^"]+)"\s+tag', text, re.IGNORECASE)
            for tag in reversed(adds_matches):
                tag_clean = tag.strip().lower()
                if tag_clean in tag_phase_map:
                    node['pipeline_change'] = tag_phase_map[tag_clean]
                    break
        # Check for step-to-phase mapping (for steps whose tags are in automations, not step text)
        if not node['pipeline_change'] and '__step_map__' in tag_phase_map:
            desc_low = node['description'].lower()
            for keyword, phase in tag_phase_map['__step_map__']:
                if keyword in desc_low:
                    node['pipeline_change'] = phase
                    break

    return node


# ─── HTML BUILDERS ────────────────────────────────────────

def build_step_li(steps):
    """Build numbered step <li> elements."""
    out = []
    for i, s in enumerate(steps, 1):
        out.append(f'              <li><span class="step-num">{i}</span>{esc(s)}</li>')
    return '\n'.join(out)

def build_workflow_item(name, stages, desc, steps_raw):
    """Build one expandable workflow item."""
    steps = parse_steps(steps_raw)
    cname = clean_name(name)
    return f'''        <div class="workflow-item">
          <div class="workflow-header" onclick="toggleWorkflow(this)">
            <div class="workflow-header-left">
              <div class="workflow-dot"></div>
              <span class="workflow-name">{esc(cname)}</span>
              <span class="workflow-tag">{stages or len(steps)} stages</span>
            </div>
            <span class="workflow-toggle">▾</span>
          </div>
          <div class="workflow-body">
            <p>{esc(desc or "")}</p>
            <ul class="workflow-steps">
{build_step_li(steps)}
            </ul>
          </div>
        </div>'''

def build_workflow_card(group_label, wf_items_html):
    """Wrap workflow items in a card with a group title."""
    return f'''    <div class="card">
      <div class="card-title">{esc(group_label)}</div>
      <div class="workflow-list">
{wf_items_html}
      </div>
    </div>'''

def split_auto_by_path(items):
    """Split automation items into sub-groups by path (Theatre, Headshot, Event, etc.).
    Returns list of (sub_label, sub_items). Items matching multiple paths appear in each."""
    paths = [
        ('Theatre', ['theatre']),
        ('Events', ['event']),
        ('Headshots', ['headshot']),
    ]
    buckets = {p: [] for p, _ in paths}
    for item in items:
        low = item.lower()
        matched = [p for p, keywords in paths if any(k in low for k in keywords)]
        if matched:
            for p in matched:
                buckets[p].append(item)
        else:
            pass
    result = []
    for p, _ in paths:
        if buckets[p]:
            result.append((p, buckets[p]))
    return result


def build_auto_group(name, count, desc, items_raw, split_by_path=False):
    """Build one automation group as a standalone card, optionally split by path."""
    items = parse_steps(items_raw) if isinstance(items_raw, str) else items_raw
    icon_map = {
        'Booking Automations': '📅',
        'Lead Capture': '🎯',
        'Pipeline Phase Movements': '🗂️',
        'Workflow Automations': '⚡',
        'Document Automations': '📄',
    }
    icon = icon_map.get(name, '⚙️')

    if split_by_path and len(items) > 4:
        sub_groups = split_auto_by_path(items)
        if len(sub_groups) > 1:
            body_html = ''
            for sub_label, sub_items in sub_groups:
                sub_items_html = ''
                for item in sub_items:
                    sub_items_html += f'          <div class="at-item"><span class="at-bullet">⚡</span><span>{esc(item)}</span></div>\n'
                body_html += f'''      <div class="at-subgroup">
        <div class="at-subgroup-label">{esc(sub_label)} <span style="color:var(--text-light); font-weight:400;">· {len(sub_items)}</span></div>
{sub_items_html}      </div>\n'''
            return f'''    <div class="card">
      <div class="card-title at-toggle" onclick="this.classList.toggle('open')">{icon} {esc(name)} <span style="font-size:12px; color:var(--text-light); font-weight:400;">· {count}</span><span class="at-arrow">▶</span></div>
      <div class="at-body">
      <p style="font-size:12.5px; color:var(--text-light); margin-bottom:14px; line-height:1.5;">{esc(desc)}</p>
{body_html}      </div>
    </div>'''

    items_html = ''
    for item in items:
        items_html += f'''          <div class="at-item"><span class="at-bullet">⚡</span><span>{esc(item)}</span></div>\n'''

    return f'''    <div class="card">
      <div class="card-title at-toggle" onclick="this.classList.toggle('open')">{icon} {esc(name)} <span style="font-size:12px; color:var(--text-light); font-weight:400;">· {count}</span><span class="at-arrow">▶</span></div>
      <div class="at-body">
      <p style="font-size:12.5px; color:var(--text-light); margin-bottom:14px; line-height:1.5;">{esc(desc)}</p>
      <div class="at-list">
{items_html}      </div>
      </div>
    </div>'''

def build_detail_row(label, value):
    """Build a copper-label / value detail row."""
    return f'''            <div style="display:flex; gap:10px; font-size:13px; color:var(--text-mid); line-height:1.5;">
              <span style="color:var(--copper); font-weight:500; white-space:nowrap; min-width:160px;">{esc(label)}</span>
              <span style="color:var(--text-light); font-style:italic;">{esc(value)}</span>
            </div>'''


def _svc_detail_val(details, key):
    """Find a value by key (case-insensitive) in a list of (label, value) pairs."""
    for k, v in details:
        if key.lower() in k.lower():
            return v
    return ''


def _extract_price(payments_str):
    """Pull the first dollar amount from a payments string."""
    if not payments_str:
        return ''
    m = re.search(r'\$[\d,]+(?:\.\d{2})?', payments_str)
    return m.group(0) if m else ''


def _extract_questions_summary(questions_str):
    """Turn a long questions string into short pill labels."""
    if not questions_str or questions_str.lower() == 'n/a':
        return []
    parts = re.split(r';\s*', questions_str)
    pills = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        p = re.sub(r'\(maps to [^)]+\)', '', p).strip()
        p = re.sub(r'\(text\)', '', p).strip()
        p = re.sub(r'\(Optional\)', '', p, flags=re.IGNORECASE).strip()
        if len(p) > 30:
            p = p[:28] + '…'
        if p:
            pills.append(p)
    return pills


def build_booking_service(name, details):
    """Build one service card group: a duration mini-card + main details card."""
    duration = _svc_detail_val(details, 'Duration')
    buffers = _svc_detail_val(details, 'Buffer')
    payments = _svc_detail_val(details, 'Payments')
    location = _svc_detail_val(details, 'Location')
    proj_mgmt = _svc_detail_val(details, 'Project management')
    confirm = _svc_detail_val(details, 'Confirmation')
    questions = _svc_detail_val(details, 'Questions')
    messaging = _svc_detail_val(details, 'Messaging')
    reminder = _svc_detail_val(details, 'Reminder')

    # Duration mini-card
    dur_card = ''
    if duration:
        dur_display = esc(duration)
        buf_html = ''
        if buffers and buffers.lower() != 'n/a':
            buf_html = f'<div style="font-size:10px; color:var(--text-light); margin-top:4px;">+ {esc(buffers)}</div>'
        dur_card = f'''<div class="bk-dur-card">
          <div style="font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-light); margin-bottom:4px;">Duration</div>
          <div style="font-size:16px; font-weight:600; color:var(--green);">{dur_display}</div>{buf_html}
        </div>'''

    # Price + payment description
    price = _extract_price(payments)
    price_line = ''
    if price:
        pay_desc = esc(payments) if payments and payments.lower() != 'none' else ''
        price_line = f'<div class="bk-svc-price">{esc(price)}</div>'
        if pay_desc:
            price_line += f'<div style="font-size:11px; color:var(--text-light); margin-bottom:8px;">{pay_desc}</div>'

    rows = []
    if payments and not price:
        if payments.lower() != 'none':
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Payment</span><span class="bk-svc-value">{esc(payments)}</span></div>')
    if payments and price:
        deposit_info = ''
        if 'due at booking' in payments.lower():
            m = re.search(r'\$[\d,]+(?:\.\d{2})?\s+due at booking', payments, re.IGNORECASE)
            deposit_info = m.group(0) if m else ''
        elif 'pay in full' in payments.lower():
            deposit_info = 'Pay in full'
        if deposit_info:
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Deposit</span><span class="bk-svc-value">{esc(deposit_info)}</span></div>')
    if location and location.lower() != 'n/a':
        rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Location</span><span class="bk-svc-value">{esc(location)}</span></div>')
    if messaging and messaging.lower() != 'n/a':
        rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Terms note</span><span class="bk-svc-value" style="font-style:italic; font-size:11px;">{esc(messaging)}</span></div>')
    if proj_mgmt and proj_mgmt.lower() != 'n/a':
        tags = re.findall(r'"([^"]+)"', proj_mgmt)
        if tags:
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">⚡ Tags</span><span class="bk-svc-value">{esc(", ".join(tags))}</span></div>')
    if confirm and confirm.lower() != 'n/a':
        cal_parts = [p.strip() for p in re.split(r'[,;]', confirm) if 'calendar' in p.lower()]
        if cal_parts:
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">⚡ Calendar</span><span class="bk-svc-value">{esc("; ".join(cal_parts))}</span></div>')
        wf_match = re.search(r'(?:WILL\s+)?(?:start|starts|START)\s+(?:NEW\s+)?(.+?)\s*WORKFLOW', confirm, re.IGNORECASE)
        if wf_match:
            wf_name = wf_match.group(1).strip()
            wf_label = f'Starts {wf_name} workflow' if wf_name.upper() != 'NEW' and wf_name else 'Starts new workflow'
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">⚡ After booking</span><span class="bk-svc-value">{esc(wf_label)}</span></div>')
    if reminder and reminder.lower() not in ('n/a', ''):
        if 'workflow' in reminder.lower():
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Reminders</span><span class="bk-svc-value">handled in workflow</span></div>')
        else:
            rows.append(f'<div class="bk-svc-row"><span class="bk-svc-label">Reminders</span><span class="bk-svc-value">{esc(reminder)}</span></div>')

    # Intake questions
    q_pills = _extract_questions_summary(questions)
    q_html = ''
    if q_pills:
        pills_html = ' '.join([f'<span class="bk-q-pill">{esc(q)}</span>' for q in q_pills])
        q_html = f'''<div style="margin-top:10px; padding-top:10px; border-top:1px solid var(--border);">
            <div style="font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-light); margin-bottom:8px;">Intake questions</div>
            <div class="bk-q-list">{pills_html}</div>
          </div>'''

    rows_html = '\n          '.join(rows)

    main_card = f'''<div class="bk-svc-card" style="flex:1;">
          <div class="bk-svc-name">{esc(name)}</div>
          {price_line}
          {rows_html}
          {q_html}
        </div>'''

    return f'''        <div class="bk-svc-group">
          {dur_card}
          {main_card}
        </div>'''


def build_booking_schedule(sched_name, sched_url, details, services):
    """Build one complete booking schedule card (redesigned)."""
    details_dict = {k.lower(): v for k, v in details}

    avail = details_dict.get('general availability', '')
    avail_tag = f'<span class="bk-avail-tag">{esc(avail)}</span>' if avail else ''

    url_btn = f'''<div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <a href="{esc(sched_url)}" target="_blank" class="btn btn-outline" style="font-size:12px;">Open scheduling page →</a>
        <button class="btn btn-outline" style="font-size:12px; cursor:pointer;" onclick="navigator.clipboard.writeText('{esc(sched_url)}');this.textContent='Copied!';setTimeout(()=>this.textContent='📋 Copy link',1500)">📋 Copy link</button>
      </div>''' if sched_url else ''

    rule_map = [
        ("can't book with less than", 'Min notice'),
        ("can't book out more than", 'Max advance'),
        ('limit(s) per day/week', 'Daily limit'),
        ('prevent cancelling within', 'Cancel cutoff'),
        ('calendars cross-checked', 'Cross-checked calendars'),
    ]
    rules_html = ''
    for detail_key, label in rule_map:
        val = details_dict.get(detail_key, '')
        if not val:
            continue
        display_val = val
        if label == 'Cross-checked calendars':
            parts = [p.strip().split(' - ')[-1] for p in val.split(',')]
            display_val = ', '.join(parts)
        rules_html += f'''        <div class="bk-rule">
          <div class="bk-rule-label">{esc(label)}</div>
          <div class="bk-rule-value">{esc(display_val)}</div>
        </div>\n'''

    service_items = '\n'.join([build_booking_service(n, d) for n, d in services])

    return f'''    <div class="card">
      <div class="bk-sched-header">
        <div>
          <div class="card-title" style="margin-bottom:4px;">📅 {esc(sched_name)}</div>
          {avail_tag}
        </div>
        {url_btn}
      </div>
      <div class="bk-rules">
{rules_html}      </div>
      <div class="bk-svc-grid">
{service_items}
      </div>
    </div>'''

def build_session_card(num, topic, date_str, url, notes_raw, passcode='', summary_url='', action_items=None):
    """Build one zoom session card."""
    date_display = format_date_display(date_str)
    btns = ''
    if url:
        btns += f'<a href="{esc(url)}" target="_blank" class="btn btn-copper" style="font-size:12px;">▶ Watch Recording</a> '
    if summary_url:
        btns += f'<a href="{esc(summary_url)}" target="_blank" class="btn btn-outline" style="font-size:12px;">📋 Meeting Summary</a>'

    passcode_html = ''
    if passcode and url:
        passcode_html = f'<div style="font-size:11px; color:var(--text-light); margin-bottom:12px;">Recording passcode: <code style="background:var(--green-pale); padding:2px 6px; border-radius:4px; font-size:12px;">{esc(passcode)}</code></div>'

    if notes_raw:
        note_lines = parse_steps(notes_raw)
        notes_html = '\n'.join([
            f'          <li style="font-size:13px; color:var(--text-mid); display:flex; gap:10px;"><span style="color:var(--copper); flex-shrink:0;">✔️</span> {esc(n)}</li>'
            for n in note_lines
        ])
        notes_section = f'''      <div style="background:var(--green-pale); border-radius:8px; padding:16px 18px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:10px;">Session Highlights</div>
        <ul style="list-style:none; display:flex; flex-direction:column; gap:8px;">
{notes_html}
        </ul>
      </div>'''
    else:
        placeholder = 'Recording link and notes will be added after the session.' if not url else ''
        notes_section = ''
        if placeholder:
            notes_section = f'''      <div style="background:var(--green-pale); border-radius:8px; padding:16px 18px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:10px;">Session Notes</div>
        <p style="font-size:13px; color:var(--text-light); font-style:italic;">{placeholder}</p>
      </div>'''

    action_section = ''
    if action_items:
        items_html = ''
        for idx, item in enumerate(action_items):
            cb_id = f's{num}-action-{idx}'
            items_html += f'''          <label class="action-item" for="{cb_id}">
            <input type="checkbox" id="{cb_id}" onchange="saveCheckbox(this)">
            <span>{esc(item)}</span>
          </label>\n'''
        action_section = f'''      <div style="background:rgba(184,125,82,0.08); border:1px solid rgba(184,125,82,0.2); border-radius:8px; padding:16px 18px; margin-top:12px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--copper); margin-bottom:10px;">Your Action Items</div>
{items_html}      </div>'''

    return f'''    <div class="card">
      <div class="card-title">🎥 Session {num} · {esc(topic or "Untitled")}</div>
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
        <span style="font-size:12px; color:var(--text-light); letter-spacing:0.05em;">{esc(date_display or "Date TBD")}</span>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">{btns}</div>
      </div>
      {passcode_html}
{notes_section}
{action_section}
    </div>'''

def build_pipeline_card(name, phase_count, image_url, phases_data=None):
    """Build one pipeline card with phase flow and screenshot."""
    if phases_data:
        phase_cards = []
        for i, ph in enumerate(phases_data):
            triggers = []
            for e in ph['entries']:
                triggers.append(f'➡️ {esc(e)}')
            for x in ph['exits']:
                triggers.append(f'⬅️ {esc(x)}')
            trigger_html = '<br>'.join(triggers) if triggers else '<em>—</em>'

            wf_html = ''
            for wt in ph.get('wf_tags', []):
                wf_html += f'\n              <span class="pl-wf-tag">{esc(wt)}</span>'

            is_last = (i == len(phases_data) - 1)

            phase_cards.append(f'''          <div class="pl-phase">
            <div class="pl-phase-name">{esc(ph['name'])}</div>
            <div class="pl-phase-trigger">{trigger_html}</div>{wf_html}
          </div>''')

            if not is_last:
                phase_cards.append('          <div class="pl-arrow">→</div>')

        flow_html = f'''      <div class="pl-flow">
{chr(10).join(phase_cards)}
      </div>'''
    else:
        flow_html = ''

    img_html = ''
    if image_url:
        img_html = f'''
      <img src="{esc(image_url)}" alt="{esc(name)} Pipeline" style="width:100%; border-radius:8px; border:1px solid var(--border); margin-top:12px;">'''

    phase_names = ''
    if phases_data:
        phase_names = ' → '.join([ph['name'] for ph in phases_data])
        phase_names = f'<div class="pl-summary">{esc(phase_names)}</div>'

    return f'''    <div class="card pl-card">
      <div class="card-title pl-toggle" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('open');">🗂️ {esc(name)} Pipeline <span style="font-size:12px; color:var(--text-light); font-weight:400;">· {esc(str(phase_count))} phases</span> <span class="pl-expand-arrow">▶</span></div>
      {phase_names}
      <div class="pl-detail">
{flow_html}{img_html}
      </div>
    </div>'''


# ─── JOURNEY MAP BUILDERS ────────────────────────────────

def build_journey_row(node):
    """Build one 3-column row for the journey map (timing | step | pipeline)."""
    cls_map = {'manual': '', 'automated': ' auto', 'email': ' email', 'client_action': ' client'}
    cls = cls_map.get(node['type'], ' auto')

    if node['type'] == 'manual' and node['member_emoji']:
        icon = node['member_emoji']
    elif node['type'] == 'email':
        icon = '⚡📧' if node.get('is_auto_email') else '📧'
    elif node['type'] == 'client_action':
        icon = '⏸️'
    else:
        icon = '⚡'

    if node['member_name']:
        mbg = hex_to_rgba(node['member_color']) if node['member_color'] else 'rgba(0,0,0,0.06)'
        tag_html = f'<span class="jt-who" style="background:{mbg};color:{node["member_color"]}">{esc(node["member_name"])}</span>'
    elif node.get('is_auto_email'):
        tag_html = '<span class="jt-email-tag">auto to client</span>'
    elif node['type'] == 'email':
        tag_html = '<span class="jt-email-tag">client receives</span>'
    elif node['type'] == 'client_action':
        tag_html = '<span class="jt-email-tag">client action</span>'
    elif node['type'] == 'automated':
        tag_html = '<span class="jt-auto-tag">auto</span>'
    else:
        tag_html = ''

    timing_html = esc(node['timing']) if node['timing'] else ''
    pipeline_html = f'→ {esc(node["pipeline_change"])}' if node['pipeline_change'] else ''

    return f'''              <div class="jt-row">
                <div class="jt-timing">{timing_html}</div>
                <div class="jt-step{cls}">
                  <span class="jt-icon">{icon}</span>
                  <span class="jt-desc">{esc(node["description"])}</span>
                  {tag_html}
                </div>
                <div class="jt-pipeline">{pipeline_html}</div>
              </div>'''


def build_journey_branch(idx, label, wf_nums, all_wf, team_members, tag_phase_map=None):
    """Build one journey branch tab content."""
    html = ''
    for wi, wf_num in enumerate(wf_nums):
        if wf_num not in all_wf:
            continue
        wf = all_wf[wf_num]
        wf_name = clean_name(wf['name'])
        steps = parse_steps(wf['steps'])

        html += f'            <div class="jt-wf-label">{esc(wf_name)}</div>\n'
        html += '            <div class="jt-col-header"><span>Timing</span><span>Step</span><span>Pipeline</span></div>\n'

        transition_target = ''
        for step_text in steps:
            node = classify_journey_step(step_text, team_members, tag_phase_map)
            if node['is_transition']:
                transition_target = node['transition_target']
                continue
            html += build_journey_row(node) + '\n'

        if transition_target and wi < len(wf_nums) - 1:
            html += f'            <div class="jt-transition">↓ Flows into: {esc(transition_target)}</div>\n'

    active = ' active' if idx == 0 else ''
    return f'          <div class="journey-branch{active}" id="jb-{idx}">\n{html}          </div>'


def build_journey_section(journey_branches, all_wf, team_members, lead_capture_items, lc_form_fields=None, tag_phase_map=None):
    """Build the complete Client Experience section HTML."""
    member_dots = ''
    for mname, minfo in team_members.items():
        c = minfo.get('color', '#888')
        e = minfo.get('emoji', '')
        member_dots += f'<span class="legend-item"><span class="legend-dot" style="background:{c}"></span> {esc(mname)}</span>\n            '

    legend = f'''    <div class="card jt-legend-card" style="padding:16px 20px; margin-bottom:20px;">
      <div class="journey-legend">
        <div class="legend-group">
          <span class="legend-label">Team</span>
          {member_dots.strip()}
        </div>
        <div class="legend-group">
          <span class="legend-label">Step type</span>
          <span class="legend-item"><span class="legend-swatch legend-sw-auto"></span> Automated</span>
          <span class="legend-item"><span class="legend-swatch legend-sw-client"></span> Client touchpoint</span>
        </div>
      </div>
    </div>''' if team_members else ''

    entry_items = '\n'.join(f'        <div class="journey-entry-item">⚡ {esc(item)}</div>' for item in lead_capture_items)

    tabs = '\n'.join(
        f'          <button class="journey-tab{" active" if i == 0 else ""}" onclick="showJourneyBranch({i})">{esc(label)}</button>'
        for i, (label, _) in enumerate(journey_branches)
    )

    branches = '\n'.join(
        build_journey_branch(i, label, nums, all_wf, team_members, tag_phase_map)
        for i, (label, nums) in enumerate(journey_branches)
    )

    return f'''
  <!-- ══════ CLIENT EXPERIENCE ══════ -->
  <section class="page-section" id="client-experience">
    <div class="section-header">
      <h1>Client Experience</h1>
      <p>The complete journey from first inquiry to final delivery — who does what, when, and what the client sees along the way.</p>
    </div>

{legend}

    <div class="card jt-entry-card" style="text-align:center;">
      <div style="font-size:18px; font-weight:600; color:var(--cb-primary); margin-bottom:14px;">Lead Submits Inquiry</div>
{'      <div style="margin-bottom:16px;"><div style="font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:var(--copper); font-weight:500; margin-bottom:8px;">Info gathered from client</div><div class="bk-q-list" style="justify-content:center;">' + ''.join(f'<span class="bk-q-pill">{esc(f)}</span>' for f in lc_form_fields) + '</div></div>' if lc_form_fields else ''}
      <div style="display:flex; flex-direction:column; gap:6px; text-align:left; max-width:420px; margin:0 auto;">
{entry_items}
      </div>
    </div>
    <div style="width:2px; height:20px; background:var(--cb-accent1); margin:0 auto;"></div>

    <div class="journey-tabs-container">
      <div class="journey-tabs">
{tabs}
      </div>
      <div class="journey-branches-wrap">
{branches}
      </div>
    </div>
  </section>
'''


def build_journey_context_text(journey_branches, all_wf, team_members, lead_capture_items):
    """Build plain text journey summary for CLIENT_CONTEXT."""
    ctx = '\nCLIENT JOURNEY (Client Experience Map):\n'
    ctx += '\nWhen a lead submits the inquiry form:\n'
    for item in lead_capture_items:
        ctx += f'  - {item}\n'

    if team_members:
        ctx += '\nTeam Members:\n'
        for mname, minfo in team_members.items():
            ctx += f'  {minfo.get("emoji", "")} {mname}\n'

    for label, wf_nums in journey_branches:
        ctx += f'\n{label} PATH:\n'
        for wf_num in wf_nums:
            if wf_num not in all_wf:
                continue
            wf = all_wf[wf_num]
            wf_name = clean_name(wf['name'])
            steps = parse_steps(wf['steps'])
            ctx += f'\n  [{wf_name}]\n'
            for si, step in enumerate(steps, 1):
                node = classify_journey_step(step, team_members)
                prefix = f'{node["member_emoji"]} {node["member_name"]}' if node['member_name'] else '⚡ AUTO'
                ctx += f'    {si}. [{prefix}] {node["description"]}'
                if node['timing']:
                    ctx += f' ({node["timing"]})'
                if node['pipeline_change']:
                    ctx += f' → Pipeline: {node["pipeline_change"]}'
                ctx += '\n'

    return ctx


# ─── CLIENT CONTEXT BUILDER ──────────────────────────────

def build_client_context(d, workflows, auto_groups_data, booking_schedules):
    """Build the CLIENT_CONTEXT string for Robot Nicole."""
    name = d.get('Client Business Name', '')
    setup = format_month_year(d.get('date:Setup Date:start', ''))
    biz = d.get('Business Type', '')
    special = d.get('Special Notes', '')

    ctx = f'''You are an AI assistant built into a private client portal created by Nicole at Let Nicole Help (letnicolehelp.com), a 17hats setup specialist.

CLIENT NAME: {name}
SETUP DATE: {setup}
BUSINESS TYPE: {biz}

DAILY WORKFLOW:
{special}

PIPELINES:'''

    for i in range(1, 13):
        pname = d.get(f'Pipeline {i} Name', '')
        pphases = d.get(f'Pipeline {i} Phases', '')
        if pname:
            ctx += f'\n{i}. {pname} Pipeline ({pphases} phases)'

    ctx += '\n\nWORKFLOWS BUILT:\n'
    for num in range(1, 13):
        wname = clean_name(d.get(f'Workflow {num} Name', ''))
        wdesc = d.get(f'Workflow {num} Description', '')
        wstages = d.get(f'Workflow {num} Stages', '')
        wsteps = d.get(f'Workflow {num} Steps', '')
        if not wname: continue
        steps = parse_steps(wsteps)
        steps_text = ' → '.join(steps) if steps else ''
        ctx += f'\n{num}. {wname} ({wstages} stages): {wdesc}'
        if steps_text:
            ctx += f'\n   Steps: {steps_text}'
        ctx += '\n'

    # Automations
    for label in ['Lead Capture', 'Pipelines', 'Workflows', 'Documents']:
        raw = d.get(f'Automations - {label}', '')
        if not raw or raw == 'TBD': continue
        items = parse_steps(raw)
        ctx += f'\n{label.upper()} AUTOMATIONS:\n'
        for item in items:
            ctx += f'- {item}\n'

    # Bookings
    if booking_schedules:
        ctx += '\nBOOKING SCHEDULES:\n'
        for i, (sname, surl, details, services) in enumerate(booking_schedules, 1):
            ctx += f'\n{i}. {sname} ({surl})\n'
            for k, v in details:
                ctx += f'   {k}: {v}\n'
            for svc_name, svc_details in services:
                ctx += f'   Service: {svc_name}\n'
                for k, v in svc_details:
                    ctx += f'   - {k}: {v}\n'

    # Tips
    ctx += '\nKEY TIPS:\n'
    for i in range(1, 5):
        tip = d.get(f'Quick Tip {i}', '')
        if tip:
            tip = tip.replace('\\\\~', '~').replace('\\~', '~').strip('*').strip()
            ctx += f'- {tip}\n'

    ctx += '''
Your role: Answer questions about this client\'s specific 17hats setup, general 17hats how-to questions, and help them navigate their workflows. If asked something outside your knowledge, suggest they contact Nicole directly at letnicolehelp.com or visit the 17hats help center at help.17hats.com.

Always be warm, helpful, and specific. Reference their actual setup when relevant. Keep responses concise but complete. Do NOT make up specific features or details you don\'t know.'''

    return ctx


# ─── MAIN GENERATOR ──────────────────────────────────────

def generate_portal(data_path, output_path):
    with open(data_path, 'r', encoding='utf-8') as f:
        d = json.load(f)

    # ── Extract key values ──
    name = d.get('Client Business Name', 'Client')
    password = d.get('Portal Password', 'CHANGE_ME')
    client_key = d.get('Client Key', '') or make_client_key(name)
    industry = d.get('Portal Industry', 'General')
    biz_type = d.get('Business Type', '')
    logo_url = d.get('Logo URL', '')
    setup_date = d.get('date:Setup Date:start', '')
    setup_month_year = format_month_year(setup_date)
    setup_year = setup_date[:4] if setup_date else '2026'
    checkin_date = d.get('date:Next Check-In Date:start', '')
    checkin_label = d.get('Next Check-In Label', '') or format_checkin_label(checkin_date)
    overview = d.get('Overview Summary', '')
    num_wf = int(d.get('Num Workflows', 0) or 0)
    num_pl = int(d.get('Num Pipelines', 0) or 0)
    num_auto = 0  # computed after auto_groups is built

    today = datetime.now().strftime('%B %d, %Y').replace(' 0', ' ')
    today_iso = datetime.now().strftime('%Y-%m-%dT00:00:00Z')

    # ── Build workflows ──
    all_wf = {}
    for i in range(1, 13):
        wname = d.get(f'Workflow {i} Name', '')
        if not wname: continue
        all_wf[i] = {
            'name': wname,
            'desc': d.get(f'Workflow {i} Description', ''),
            'stages': int(d.get(f'Workflow {i} Stages', 0) or 0),
            'steps': d.get(f'Workflow {i} Steps', ''),
        }

    wf_groups_raw = d.get('Workflow Groups', '')
    wf_groups = parse_workflow_groups(wf_groups_raw)

    if wf_groups:
        workflows_html = ''
        for label, nums in wf_groups:
            items_html = ''
            for n in nums:
                if n in all_wf:
                    w = all_wf[n]
                    items_html += build_workflow_item(w['name'], w['stages'], w['desc'], w['steps']) + '\n'
            if items_html:
                workflows_html += build_workflow_card(label, items_html) + '\n\n'
    else:
        # No grouping defined; put all workflows in one card
        items_html = ''
        for n in sorted(all_wf.keys()):
            w = all_wf[n]
            items_html += build_workflow_item(w['name'], w['stages'], w['desc'], w['steps']) + '\n'
        workflows_html = build_workflow_card('All Workflows', items_html)

    # ── Build booking automations from schedule data ──
    booking_auto_items = []
    for i in range(1, 13):
        sname = d.get(f'Booking Schedule {i} Name', '')
        if not sname:
            continue
        svcs = parse_booking_services(d.get(f'Booking Schedule {i} Services', ''))
        for svc_name, svc_details in svcs:
            proj_mgmt = _svc_detail_val(svc_details, 'Project management')
            confirm = _svc_detail_val(svc_details, 'Confirmation')
            if proj_mgmt and proj_mgmt.lower() != 'n/a':
                tags = re.findall(r'"([^"]+)"', proj_mgmt)
                if tags:
                    booking_auto_items.append(f'{svc_name}: auto-tags contact/project with {", ".join(tags)}')
            if confirm and confirm.lower() != 'n/a':
                cal_parts = [p.strip() for p in re.split(r'[,;]', confirm) if 'calendar' in p.lower()]
                if cal_parts:
                    booking_auto_items.append(f'{svc_name}: {"; ".join(cal_parts)}')
                wf_match = re.search(r'(?:WILL\s+)?(?:start|starts|START)\s+(?:NEW\s+)?(.+?)\s*WORKFLOW', confirm, re.IGNORECASE)
                if wf_match:
                    wf_name = wf_match.group(1).strip()
                    if wf_name.upper() != 'NEW' and wf_name:
                        booking_auto_items.append(f'{svc_name}: starts {wf_name} workflow')
                    else:
                        booking_auto_items.append(f'{svc_name}: starts new workflow')

    # ── Build automations ──
    auto_html = ''
    auto_groups = []

    if booking_auto_items:
        auto_html += build_auto_group('Booking Automations', len(booking_auto_items),
            'Automations triggered when a client books through a scheduling page.', booking_auto_items) + '\n'
        auto_groups.append(('Booking Automations', booking_auto_items))

    for label, field, desc, split in [
        ('Lead Capture', 'Automations - Lead Capture', 'These automations fire when a new lead submits the lead capture form.', False),
        ('Pipeline Phase Movements', 'Automations - Pipelines', 'Automatic pipeline phase changes triggered by workflow actions and time-based rules.', True),
        ('Workflow Automations', 'Automations - Workflows', 'Automated emails, tags, and workflow transitions within workflows.', True),
        ('Document Automations', 'Automations - Documents', 'Document-related automations.', False),
    ]:
        raw = d.get(field, '')
        if not raw or raw == 'TBD': continue
        items = parse_steps(raw)
        auto_html += build_auto_group(label, len(items), desc, items, split_by_path=split) + '\n'
        auto_groups.append((label, items))

    num_auto = sum(len(items) for _, items in auto_groups)

    # ── Build pipelines ──
    pipelines_raw = []
    for i in range(1, 13):
        pname = d.get(f'Pipeline {i} Name', '')
        if not pname: continue
        pphases = d.get(f'Pipeline {i} Phases', '')
        pimg = d.get(f'Pipeline {i} Image URL', '')
        pipelines_raw.append((pname, pphases, pimg))

    pipeline_auto_text = d.get('Automations - Pipelines', '')
    pipeline_data = parse_pipeline_automations(pipeline_auto_text, pipelines_raw, all_wf)

    pipelines_html = ''
    for pname, pcount, pimg, phases_data in pipeline_data:
        pipelines_html += build_pipeline_card(pname, pcount, pimg, phases_data) + '\n'

    # ── Build bookings ──
    booking_schedules = []
    bookings_html = ''
    for i in range(1, 4):
        sname = d.get(f'Booking Schedule {i} Name', '')
        if not sname: continue
        surl = d.get(f'Booking Schedule {i} URL', '')
        sdetails = parse_booking_details(d.get(f'Booking Schedule {i} Details', ''))
        sservices = parse_booking_services(d.get(f'Booking Schedule {i} Services', ''))
        booking_schedules.append((sname, surl, sdetails, sservices))
        bookings_html += build_booking_schedule(sname, surl, sdetails, sservices) + '\n'

    has_bookings = bool(bookings_html.strip())

    # ── Build sessions ──
    sessions_html = ''
    for i in range(1, 4):
        topic = d.get(f'Session {i} Topic', '')
        if not topic: continue
        sdate = d.get(f'date:Session {i} Date:start', '')
        surl = d.get(f'Session {i} Recording URL', '')
        snotes = d.get(f'Session {i} Notes', '')
        spcode = d.get(f'Session {i} Recording Passcode', '')
        ssum_url = d.get(f'Session {i} Summary URL', '')
        s_actions_raw = d.get(f'Session {i} Action Items', '')
        s_actions = [a.strip() for a in s_actions_raw.split('|') if a.strip()] if s_actions_raw else None
        sessions_html += build_session_card(i, topic, sdate, surl, snotes, passcode=spcode, summary_url=ssum_url, action_items=s_actions) + '\n'

    # ── Build tips ──
    tips_html = ''
    for i in range(1, 5):
        tip = d.get(f'Quick Tip {i}', '')
        if not tip: continue
        tip = tip.replace('\\\\~', '~').replace('\\~', '~').strip('*').strip()
        tips_html += f'          <li style="font-size:13px; color:var(--text-mid); display:flex; gap:10px; align-items:flex-start;"><span style="color:var(--copper); flex-shrink:0;">✦</span> {esc(tip)}</li>\n'

    # ── Logo HTML ──
    if logo_url:
        logo_topbar = f'''<img src="{esc(logo_url)}" alt="{esc(name)}" class="client-logo" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
      <div class="client-logo-placeholder" style="display:none;">{esc(name)}</div>'''
    else:
        logo_topbar = f'<div class="client-logo-placeholder">{esc(name)}</div>'

    # ── Bookings nav item ──
    bookings_nav = f'''    <a class="nav-item" onclick="showSection('bookings')">
      <span class="icon">📅</span> Bookings
    </a>''' if has_bookings else ''

    # ── Bookings section ──
    bookings_section = f'''
  <!-- ══════ BOOKINGS ══════ -->
  <section class="page-section" id="bookings">
    <div class="section-header">
      <h1>Bookings</h1>
      <p>Your scheduling pages and the services configured within each one.</p>
    </div>

{bookings_html}
  </section>
''' if has_bookings else ''

    # ── Build journey ──
    team_members = parse_team_members(d)
    jb_raw = d.get('Journey Branches', '')
    if not jb_raw:
        jb_raw = d.get('Workflow Groups', '')
    journey_branches = parse_workflow_groups(jb_raw) if jb_raw else []
    lead_capture_items = parse_steps(d.get('Automations - Lead Capture', ''))
    lc_fields_raw = d.get('Lead Capture Form Fields', '')
    lc_fields = [f.strip() for f in lc_fields_raw.split(';') if f.strip()] if lc_fields_raw else []

    if journey_branches:
        pipeline_auto_text = d.get('Automations - Pipelines', '')
        workflow_auto_text = d.get('Automations - Workflows', '')
        tag_phase_map = parse_tag_to_phase_map(pipeline_auto_text, workflow_auto_text)
        journey_section = build_journey_section(journey_branches, all_wf, team_members, lead_capture_items, lc_form_fields=lc_fields, tag_phase_map=tag_phase_map)
        journey_nav = '''    <a class="nav-item" onclick="showSection('client-experience')">
      <span class="icon">🗺️</span> Client Experience
    </a>'''
        workflows_nav = ''
    else:
        journey_section = ''
        journey_nav = ''
        workflows_nav = '''    <a class="nav-item" onclick="showSection('workflows')">
      <span class="icon">⟳</span> Workflows
    </a>'''

    # ── Team members HTML for overview ──
    team_html = ''
    if team_members:
        members_items = ''
        for mname, minfo in team_members.items():
            color = minfo.get('color', '#888')
            emoji = minfo.get('emoji', '')
            if emoji:
                members_items += f'<div class="tm-member"><span class="tm-name">{emoji} {esc(mname)}</span></div>\n'
            else:
                members_items += f'<div class="tm-member"><span class="tm-dot" style="background:{color};"></span><span class="tm-name">{esc(mname)}</span></div>\n'
        team_html = f'''
        <div style="margin-top:16px;">
          <div style="font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:8px;">Your Team</div>
          <div class="tm-row">{members_items}</div>
        </div>'''

    # ── Special notes HTML ──
    special_notes = d.get('Special Notes', '')
    special_notes_card = ''
    if special_notes:
        note_sentences = [s.strip() for s in re.split(r'[.;]', special_notes) if s.strip()]
        note_sentences = [s[0].upper() + s[1:] if s else s for s in note_sentences]
        notes_items = '\n'.join([
            f'          <li class="sn-item"><span class="sn-icon">▸</span> {esc(s)}</li>'
            for s in note_sentences
        ])
        special_notes_card = f'''
    <div class="card sn-card">
      <div class="card-title">📌 How to Use Your Setup</div>
      <ul class="sn-list">
{notes_items}
      </ul>
    </div>'''

    cb_primary = d.get('Client Brand Primary', '')
    cb_accent1 = d.get('Client Brand Accent 1', '')
    cb_accent2 = d.get('Client Brand Accent 2', '')
    cb_vars = ''
    if cb_primary:
        cb_vars += f'--cb-primary:{cb_primary}; --cb-primary-pale:{hex_to_rgba(cb_primary, "0.08")}; --cb-primary-light:{hex_to_rgba(cb_primary, "0.5")};'
    if cb_accent1:
        cb_vars += f' --cb-accent1:{cb_accent1}; --cb-accent1-pale:{hex_to_rgba(cb_accent1, "0.08")};'
    if cb_accent2:
        cb_vars += f' --cb-accent2:{cb_accent2};'
    if not cb_primary:
        cb_vars = '--cb-primary:var(--green); --cb-primary-pale:var(--green-pale); --cb-primary-light:var(--green-light); --cb-accent1:var(--copper); --cb-accent1-pale:var(--copper-pale); --cb-accent2:var(--copper-light);'
    else:
        if not cb_accent1:
            cb_vars += ' --cb-accent1:var(--copper); --cb-accent1-pale:var(--copper-pale);'
        if not cb_accent2:
            cb_vars += ' --cb-accent2:var(--copper-light);'

    journey_css = f'''  #client-experience {{ {cb_vars} }}
  .journey-legend {{ display:flex; flex-wrap:wrap; gap:16px; align-items:center; }}
  .legend-group {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .legend-label {{ font-size:10px; letter-spacing:0.12em; text-transform:uppercase; color:var(--text-light); margin-right:4px; }}
  .legend-dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
  .legend-item {{ display:inline-flex; align-items:center; gap:4px; font-size:12px; color:var(--text-mid); }}
  .legend-swatch {{ display:inline-block; width:16px; height:4px; border-radius:2px; }}
  .legend-sw-auto {{ background:var(--cb-primary-pale); border:1px dashed var(--cb-primary-light); }}
  .legend-sw-client {{ background:var(--cb-accent1-pale); border:1px solid var(--cb-accent1); }}
  .journey-entry-item {{ font-size:13px; color:var(--text-mid); display:flex; align-items:center; gap:8px; padding:4px 0; }}
  .jt-entry-card {{ border:2px solid var(--cb-primary); background:var(--cb-primary-pale); }}
  .journey-tabs-container {{ margin-top:0; }}
  .journey-tabs {{ display:flex; background:white; border:1px solid var(--border); border-bottom:none; border-radius:12px 12px 0 0; overflow:hidden; }}
  .journey-tab {{ flex:1; padding:13px 16px; font-family:'Montserrat',sans-serif; font-size:13px; font-weight:500; background:white; border:none; cursor:pointer; color:var(--text-light); transition:all 0.2s; border-bottom:2px solid transparent; }}
  .journey-tab:hover {{ background:var(--cb-primary-pale); color:var(--text); }}
  .journey-tab.active {{ color:var(--cb-primary); border-bottom-color:var(--cb-accent1); background:var(--cb-primary-pale); }}
  .journey-branches-wrap {{ }}
  .journey-branch {{ display:none; background:white; border:1px solid var(--border); border-top:none; border-radius:0 0 12px 12px; padding:24px 20px; }}
  .journey-branch.active {{ display:block; }}
  .jt-wf-label {{ font-size:14px; font-weight:600; color:var(--cb-primary); margin:20px 0 10px; padding:8px 14px; background:#d5e3db; border-radius:8px; }}
  .jt-wf-label:first-child {{ margin-top:0; }}
  .jt-col-header {{ display:grid; grid-template-columns:100px 1fr 120px; gap:8px; padding:4px 0; margin-bottom:4px; }}
  .jt-col-header span {{ font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-mid); font-weight:500; text-align:center; }}
  .jt-col-header span:first-child {{ text-align:center; }}
  .jt-col-header span:last-child {{ text-align:center; }}
  .jt-row {{ display:grid; grid-template-columns:100px 1fr 120px; gap:8px; align-items:center; margin-bottom:6px; min-height:36px; }}
  .jt-timing {{ font-size:11px; color:var(--text-light); line-height:1.3; padding-right:4px; }}
  .jt-pipeline {{ font-size:11px; color:var(--cb-accent1); font-weight:500; text-align:right; line-height:1.3; }}
  .jt-step {{ display:flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid var(--border); border-radius:8px; background:white; min-height:36px; }}
  .jt-step.auto {{ border-style:dashed; background:var(--cb-primary-pale); }}
  .jt-step.email {{ background:var(--cb-accent1-pale); border-color:var(--cb-accent1); }}
  .jt-step.client {{ background:var(--cb-accent1-pale); border-color:var(--cb-accent1); }}
  .jt-icon {{ font-size:13px; flex-shrink:0; }}
  .jt-desc {{ flex:1; font-size:12px; color:var(--text); line-height:1.4; }}
  .jt-who {{ font-size:10px; padding:2px 8px; border-radius:10px; white-space:nowrap; font-weight:500; flex-shrink:0; }}
  .jt-auto-tag {{ font-size:10px; color:var(--cb-primary); background:var(--cb-primary-pale); padding:2px 8px; border-radius:10px; white-space:nowrap; flex-shrink:0; }}
  .jt-email-tag {{ font-size:10px; color:var(--cb-accent1); background:var(--cb-accent1-pale); padding:2px 8px; border-radius:10px; white-space:nowrap; flex-shrink:0; }}
  .jt-transition {{ margin:14px 0; padding:6px 14px; background:var(--cb-primary-pale); border:1px dashed var(--cb-primary-light); border-radius:16px; font-size:12px; color:var(--cb-primary); font-weight:500; width:fit-content; margin-left:108px; }}
  @media (max-width:768px) {{ .journey-tabs {{ flex-wrap:wrap; }} .journey-tab {{ min-width:48%; }} .jt-row {{ grid-template-columns:1fr; gap:4px; }} .jt-timing,.jt-pipeline {{ padding-left:12px; }} .jt-col-header {{ display:none; }} }}'''

    journey_js = 'function showJourneyBranch(idx){document.querySelectorAll(".journey-branch").forEach(function(b,i){if(i===idx)b.classList.add("active");else b.classList.remove("active");});document.querySelectorAll(".journey-tab").forEach(function(t,i){if(i===idx)t.classList.add("active");else t.classList.remove("active");});}'

    # ── Recommended updates ──
    setup_d = datetime.strptime(setup_date[:10], '%Y-%m-%d') if setup_date else datetime.now()
    month3 = setup_d.replace(month=setup_d.month + 3) if setup_d.month <= 9 else setup_d.replace(year=setup_d.year + 1, month=setup_d.month - 9)
    month12 = setup_d.replace(year=setup_d.year + 1)

    # ── CLIENT_CONTEXT ──
    client_context = build_client_context(d, all_wf, auto_groups, booking_schedules)
    if journey_branches:
        client_context += build_journey_context_text(journey_branches, all_wf, team_members, lead_capture_items)
    # Escape for JS string literal (backtick template)
    client_context_js = client_context.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    # ── Build setup items for change request checklist ──
    setup_items = []
    for n in sorted(all_wf.keys()):
        w = all_wf[n]
        setup_items.append(('Workflow', clean_name(w['name'])))
    for i in range(1, 13):
        pname = d.get(f'Pipeline {i} Name', '')
        if pname:
            setup_items.append(('Pipeline', f'{pname} Pipeline'))
    for i in range(1, 4):
        sname = d.get(f'Booking Schedule {i} Name', '')
        if sname:
            setup_items.append(('Booking', f'{sname} (booking schedule)'))
            svcs = parse_booking_services(d.get(f'Booking Schedule {i} Services', ''))
            for svc_name, _ in svcs:
                setup_items.append(('Service', f'{svc_name} (service)'))
    for label, field, _ in [
        ('Lead Capture', 'Automations - Lead Capture', ''),
        ('Pipeline Automations', 'Automations - Pipelines', ''),
        ('Workflow Automations', 'Automations - Workflows', ''),
    ]:
        if d.get(field, '') and d.get(field, '') != 'TBD':
            setup_items.append(('Automation', f'{label} automations'))

    setup_items_js = json.dumps([{'cat': cat, 'name': name} for cat, name in setup_items])

    # ── ASSEMBLE FULL HTML ──
    # Read the CSS from the template (it's always the same)
    portal_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>{esc(name)} | Client Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --green: #2d5246; --green-light: #3a6858; --green-pale: #eef4f1;
    --copper: #b87d52; --copper-light: #d4a57a; --copper-pale: #fdf5ed;
    --cream: #faf8f5; --text: #1e3329; --text-mid: #4a6358;
    --text-light: #8aab9a; --white: #ffffff; --border: rgba(184,125,82,0.2);
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Montserrat",sans-serif; background:var(--cream); color:var(--text); min-height:100vh; }}
  .sidebar {{ position:fixed; left:0; top:0; bottom:0; width:260px; background:var(--green); z-index:100; display:flex; flex-direction:column; padding:0 0 24px 0; overflow-y:auto; }}
  .sidebar-logo {{ padding:32px 28px 24px; border-bottom:1px solid rgba(255,255,255,0.1); }}
  .sidebar-logo .by-nicole {{ font-size:10px; letter-spacing:0.15em; text-transform:uppercase; color:var(--copper-light); margin-bottom:4px; }}
  .sidebar-logo .client-name {{ font-size:22px; font-weight:500; color:white; line-height:1.2; }}
  .sidebar-logo .portal-label {{ font-size:11px; color:rgba(255,255,255,0.45); letter-spacing:0.1em; margin-top:2px; }}
  .sidebar-section {{ padding:20px 0 8px; }}
  .sidebar-section-label {{ font-size:9px; letter-spacing:0.18em; text-transform:uppercase; color:rgba(255,255,255,0.3); padding:0 28px; margin-bottom:6px; }}
  .nav-item {{ display:flex; align-items:center; gap:12px; padding:10px 28px; cursor:pointer; transition:all 0.2s; font-size:13.5px; color:rgba(255,255,255,0.65); border-left:2px solid transparent; text-decoration:none; }}
  .nav-item:hover,.nav-item.active {{ background:rgba(255,255,255,0.07); color:white; border-left-color:var(--copper-light); }}
  .nav-item .icon {{ font-size:15px; opacity:0.8; width:18px; text-align:center; flex-shrink:0; }}
  .sidebar-footer {{ margin-top:auto; padding:20px 28px 0; border-top:1px solid rgba(255,255,255,0.1); }}
  .sidebar-footer p {{ font-size:11px; color:rgba(255,255,255,0.3); line-height:1.6; }}
  .sidebar-footer a {{ color:var(--copper-light); text-decoration:none; font-size:11px; }}
  .main {{ margin-left:260px; min-height:100vh; }}
  .topbar {{ background:white; border-bottom:1px solid var(--border); padding:16px 40px; display:flex; align-items:center; justify-content:space-between; position:sticky; top:0; z-index:50; }}
  .topbar-left {{ display:flex; align-items:center; gap:12px; }}
  .topbar-right {{ display:flex; gap:10px; }}
  .btn {{ padding:8px 18px; border-radius:6px; font-size:12.5px; font-family:"Montserrat",sans-serif; cursor:pointer; transition:all 0.2s; text-decoration:none; display:inline-flex; align-items:center; gap:6px; border:none; }}
  .btn-outline {{ background:transparent; border:1px solid var(--border); color:var(--text-mid); }}
  .btn-outline:hover {{ border-color:var(--copper); color:var(--copper); }}
  .btn-primary {{ background:var(--green); color:white; }}
  .btn-primary:hover {{ background:var(--green-light); }}
  .btn-copper {{ background:var(--copper); color:white; }}
  .btn-copper:hover {{ background:var(--copper-light); }}
  .page-section {{ display:none; padding:40px; animation:fadeIn 0.3s ease; }}
  .page-section.active {{ display:block; }}
  @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .section-header {{ margin-bottom:32px; }}
  .section-header h1 {{ font-size:36px; font-weight:500; color:var(--green); line-height:1.2; margin-bottom:6px; }}
  .section-header p {{ color:var(--text-mid); font-size:14px; line-height:1.6; }}
  .stats-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:32px; }}
  .stat-card {{ background:white; border:1px solid var(--border); border-radius:12px; padding:20px 22px; }}
  .stat-card .stat-label {{ font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:8px; }}
  .stat-card .stat-value {{ font-size:32px; font-weight:500; color:var(--green); line-height:1; }}
  .stat-card .stat-sub {{ font-size:11.5px; color:var(--text-light); margin-top:4px; }}
  .card {{ background:white; border:1px solid var(--border); border-radius:12px; padding:28px; margin-bottom:20px; }}
  .card-title {{ font-size:20px; font-weight:500; color:var(--green); margin-bottom:16px; display:flex; align-items:center; gap:10px; }}
  .workflow-list {{ display:flex; flex-direction:column; gap:12px; }}
  .workflow-item {{ border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
  .workflow-header {{ display:flex; align-items:center; justify-content:space-between; padding:14px 18px; cursor:pointer; background:#d5e3db; transition:background 0.2s; }}
  .workflow-header:hover {{ background:#c8dacf; }}
  .workflow-header-left {{ display:flex; align-items:center; gap:12px; }}
  .workflow-dot {{ width:8px; height:8px; border-radius:50%; background:var(--copper); flex-shrink:0; }}
  .workflow-name {{ font-size:14px; font-weight:500; color:var(--text); }}
  .workflow-tag {{ font-size:10.5px; background:rgba(184,125,82,0.12); color:var(--copper); padding:2px 8px; border-radius:20px; letter-spacing:0.05em; }}
  .workflow-toggle {{ font-size:13px; color:var(--text-light); transition:transform 0.2s; }}
  .workflow-toggle.open {{ transform:rotate(180deg); }}
  .workflow-body {{ display:none; padding:18px; background:white; border-top:1px solid var(--border); }}
  .workflow-body.open {{ display:block; }}
  .workflow-body p {{ font-size:13.5px; color:var(--text-mid); line-height:1.7; margin-bottom:12px; }}
  .workflow-steps {{ list-style:none; display:flex; flex-direction:column; gap:8px; }}
  .workflow-steps li {{ display:flex; align-items:flex-start; gap:10px; font-size:13px; color:var(--text-mid); line-height:1.5; }}
  .step-num {{ width:20px; height:20px; border-radius:50%; background:var(--green); color:white; font-size:10px; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:1px; }}
  .update-timeline {{ position:relative; padding-left:28px; }}
  .update-timeline::before {{ content:''; position:absolute; left:8px; top:6px; bottom:6px; width:1px; background:var(--border); }}
  .update-item {{ position:relative; margin-bottom:28px; }}
  .update-item::before {{ content:''; position:absolute; left:-24px; top:5px; width:10px; height:10px; border-radius:50%; border:2px solid var(--copper); background:var(--cream); }}
  .update-timing {{ font-size:10.5px; letter-spacing:0.1em; text-transform:uppercase; color:var(--copper); margin-bottom:5px; }}
  .update-title {{ font-size:15px; font-weight:500; color:var(--text); margin-bottom:6px; }}
  .update-desc {{ font-size:13px; color:var(--text-mid); line-height:1.6; }}
  .content-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }}
  .content-card {{ background:white; border:1px solid var(--border); border-radius:10px; overflow:hidden; text-decoration:none; display:block; transition:all 0.2s; }}
  .content-card:hover {{ border-color:var(--copper-light); transform:translateY(-2px); box-shadow:0 4px 20px rgba(45,82,70,0.08); }}
  .content-card-thumb {{ height:110px; background:var(--green); display:flex; align-items:center; justify-content:center; font-size:32px; position:relative; overflow:hidden; }}
  .content-card-thumb::after {{ content:''; position:absolute; inset:0; background:linear-gradient(135deg,rgba(184,125,82,0.2) 0%,transparent 60%); }}
  .yt-thumb {{ background:linear-gradient(135deg,#1a3d30 0%,#2d5246 100%); }}
  .content-card-body {{ padding:14px 16px; }}
  .content-card-type {{ font-size:10px; letter-spacing:0.12em; text-transform:uppercase; color:var(--copper); margin-bottom:4px; }}
  .content-card-title {{ font-size:13.5px; font-weight:500; color:var(--text); line-height:1.4; }}
  .chat-wrapper {{ background:white; border:1px solid var(--border); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; height:500px; }}
  .chat-header {{ background:var(--green); padding:16px 22px; display:flex; align-items:center; gap:12px; }}
  .chat-avatar {{ width:36px; height:36px; border-radius:50%; background:var(--copper); display:flex; align-items:center; justify-content:center; font-size:16px; flex-shrink:0; }}
  .chat-header-info h3 {{ font-size:14px; font-weight:500; color:white; }}
  .chat-header-info p {{ font-size:11px; color:rgba(255,255,255,0.5); }}
  .chat-messages {{ flex:1; overflow-y:auto; padding:22px; display:flex; flex-direction:column; gap:16px; background:var(--cream); }}
  .message {{ display:flex; gap:10px; max-width:85%; }}
  .message.user {{ align-self:flex-end; flex-direction:row-reverse; }}
  .message-bubble {{ padding:11px 15px; border-radius:12px; font-size:13.5px; line-height:1.6; }}
  .message.assistant .message-bubble {{ background:white; border:1px solid var(--border); color:var(--text); border-radius:2px 12px 12px 12px; }}
  .message.user .message-bubble {{ background:var(--green); color:white; border-radius:12px 2px 12px 12px; }}
  .message-avatar {{ width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; flex-shrink:0; margin-top:2px; }}
  .assistant-avatar {{ background:var(--copper); }}
  .user-avatar {{ background:var(--green-light); }}
  .chat-input-area {{ padding:16px; border-top:1px solid var(--border); background:white; display:flex; gap:10px; align-items:flex-end; }}
  .chat-input {{ flex:1; border:1px solid var(--border); border-radius:8px; padding:10px 14px; font-family:"Montserrat",sans-serif; font-size:13.5px; color:var(--text); resize:none; outline:none; transition:border-color 0.2s; min-height:42px; max-height:120px; }}
  .chat-input:focus {{ border-color:var(--copper-light); }}
  .chat-input::placeholder {{ color:var(--text-light); }}
  .chat-send {{ width:42px; height:42px; border-radius:8px; background:var(--green); color:white; border:none; cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:16px; transition:background 0.2s; flex-shrink:0; }}
  .chat-send:hover {{ background:var(--green-light); }}
  .chat-send:disabled {{ background:var(--text-light); cursor:not-allowed; }}
  .thinking {{ display:flex; gap:4px; padding:8px 4px; }}
  .thinking span {{ width:6px; height:6px; border-radius:50%; background:var(--copper-light); animation:bounce 1.2s infinite; }}
  .thinking span:nth-child(2) {{ animation-delay:0.2s; }}
  .thinking span:nth-child(3) {{ animation-delay:0.4s; }}
  @keyframes bounce {{ 0%,80%,100% {{ transform:translateY(0); opacity:0.4; }} 40% {{ transform:translateY(-6px); opacity:1; }} }}
  .resources-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
  .resource-card {{ background:white; border:1px solid var(--border); border-radius:10px; padding:22px; text-decoration:none; display:block; transition:all 0.2s; }}
  .resource-card:hover {{ border-color:var(--copper); transform:translateY(-2px); box-shadow:0 4px 20px rgba(45,82,70,0.08); }}
  .resource-icon {{ font-size:26px; margin-bottom:12px; }}
  .resource-title {{ font-size:14px; font-weight:500; color:var(--text); margin-bottom:6px; }}
  .resource-desc {{ font-size:12.5px; color:var(--text-light); line-height:1.5; }}
  .accent-banner {{ background:linear-gradient(135deg,var(--green) 0%,var(--green-light) 100%); border-radius:12px; padding:28px 32px; margin-bottom:28px; position:relative; overflow:hidden; display:flex; align-items:center; justify-content:space-between; }}
  .accent-banner::before {{ content:''; position:absolute; right:-20px; top:-20px; width:160px; height:160px; border-radius:50%; border:30px solid rgba(184,125,82,0.15); }}
  .accent-banner::after {{ content:''; position:absolute; right:60px; bottom:-30px; width:100px; height:100px; border-radius:50%; border:20px solid rgba(184,125,82,0.1); }}
  .accent-banner h2 {{ font-size:26px; font-weight:400; color:white; margin-bottom:6px; font-style:italic; }}
  .accent-banner p {{ font-size:13px; color:rgba(255,255,255,0.65); max-width:400px; }}
  .tag-pill {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; background:rgba(184,125,82,0.15); color:var(--copper); letter-spacing:0.05em; }}
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .pw-overlay {{ position:fixed; inset:0; background:var(--green); z-index:9999; display:flex; align-items:center; justify-content:center; flex-direction:column; padding:40px; transition:opacity 0.5s ease,visibility 0.5s ease; }}
  .pw-overlay.unlocked {{ opacity:0; visibility:hidden; pointer-events:none; }}
  .pw-overlay::before {{ content:''; position:absolute; right:-60px; top:-60px; width:320px; height:320px; border-radius:50%; border:50px solid rgba(184,125,82,0.12); }}
  .pw-overlay::after {{ content:''; position:absolute; left:-40px; bottom:-40px; width:220px; height:220px; border-radius:50%; border:35px solid rgba(184,125,82,0.08); }}
  .pw-box {{ background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); border-radius:20px; padding:48px 44px; width:100%; max-width:420px; display:flex; flex-direction:column; align-items:center; position:relative; z-index:1; backdrop-filter:blur(10px); }}
  .pw-logo {{ font-size:11px; letter-spacing:0.2em; text-transform:uppercase; color:var(--copper-light); margin-bottom:6px; }}
  .pw-client {{ font-family:'Montserrat',sans-serif; font-size:26px; font-weight:600; color:white; margin-bottom:4px; text-align:center; }}
  .pw-subtitle {{ font-size:13px; color:rgba(255,255,255,0.4); margin-bottom:36px; text-align:center; }}
  .pw-lock {{ font-size:32px; margin-bottom:20px; }}
  .pw-label {{ font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:rgba(255,255,255,0.45); align-self:flex-start; margin-bottom:8px; }}
  .pw-input {{ width:100%; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; padding:14px 18px; font-family:'Montserrat',sans-serif; font-size:15px; color:white; outline:none; letter-spacing:0.1em; transition:border-color 0.2s; margin-bottom:14px; }}
  .pw-input::placeholder {{ color:rgba(255,255,255,0.2); }}
  .pw-input:focus {{ border-color:var(--copper-light); }}
  .pw-input.shake {{ animation:shake 0.4s ease; border-color:#e07070; }}
  @keyframes shake {{ 0%,100% {{ transform:translateX(0); }} 20% {{ transform:translateX(-8px); }} 40% {{ transform:translateX(8px); }} 60% {{ transform:translateX(-5px); }} 80% {{ transform:translateX(5px); }} }}
  .pw-btn {{ width:100%; background:var(--copper); color:white; border:none; border-radius:10px; padding:14px; font-family:'Montserrat',sans-serif; font-size:14px; font-weight:600; letter-spacing:0.05em; cursor:pointer; transition:background 0.2s,transform 0.1s; margin-bottom:16px; }}
  .pw-btn:hover {{ background:var(--copper-light); }}
  .pw-btn:active {{ transform:scale(0.98); }}
  .pw-error {{ font-size:12px; color:#f0a0a0; text-align:center; min-height:18px; }}
  .pw-footer {{ margin-top:32px; font-size:11px; color:rgba(255,255,255,0.2); letter-spacing:0.08em; }}
  .client-logo {{ height:36px; width:auto; max-width:140px; object-fit:contain; display:block; }}
  .client-logo-placeholder {{ height:36px; display:flex; align-items:center; font-size:13px; font-weight:600; color:var(--green); letter-spacing:0.02em; }}
  .hamburger {{ display:none; position:fixed; top:14px; left:14px; z-index:200; width:40px; height:40px; border-radius:10px; background:var(--green); border:none; cursor:pointer; flex-direction:column; align-items:center; justify-content:center; gap:5px; box-shadow:0 2px 12px rgba(0,0,0,0.2); }}
  .hamburger span {{ display:block; width:18px; height:2px; background:white; border-radius:2px; transition:all 0.25s ease; }}
  .hamburger.open span:nth-child(1) {{ transform:translateY(7px) rotate(45deg); }}
  .hamburger.open span:nth-child(2) {{ opacity:0; }}
  .hamburger.open span:nth-child(3) {{ transform:translateY(-7px) rotate(-45deg); }}
  .mobile-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.4); z-index:98; }}
  .mobile-overlay.visible {{ display:block; }}
  .nav-badge {{ display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--copper); margin-left:6px; flex-shrink:0; box-shadow:0 0 0 2px rgba(184,125,82,0.3); animation:pulse-badge 2s infinite; }}
  .action-badge {{ display:inline-flex; align-items:center; justify-content:center; min-width:18px; height:18px; border-radius:9px; background:var(--copper); color:white; font-size:10px; font-weight:600; margin-left:6px; padding:0 5px; flex-shrink:0; }}
  @keyframes pulse-badge {{ 0%,100% {{ box-shadow:0 0 0 2px rgba(184,125,82,0.3); }} 50% {{ box-shadow:0 0 0 5px rgba(184,125,82,0); }} }}
  @media print {{ .sidebar,.hamburger,.mobile-overlay,.pw-overlay,#welcomeModal,.topbar-right {{ display:none !important; }} .main {{ margin-left:0 !important; }} .page-section {{ display:block !important; page-break-after:always; }} .workflow-body,.pl-detail {{ display:block !important; }} .pl-summary {{ display:none !important; }} body {{ background:white; }} .card {{ box-shadow:none; border:1px solid #ddd; }} }}
  @media (max-width:768px) {{ .sidebar {{ transform:translateX(-100%); transition:transform 0.3s ease; z-index:99; width:280px; }} .sidebar.mobile-open {{ transform:translateX(0); }} .hamburger {{ display:flex; }} .main {{ margin-left:0; }} .topbar {{ padding:14px 16px 14px 64px; }} .page-section {{ padding:24px 16px; }} .stats-row {{ grid-template-columns:1fr 1fr; gap:10px; }} .content-grid {{ grid-template-columns:1fr; }} .resources-grid {{ grid-template-columns:1fr 1fr; }} .two-col {{ grid-template-columns:1fr; }} .accent-banner {{ flex-direction:column; gap:16px; }} .accent-banner h2 {{ font-size:20px; }} .chat-wrapper {{ height:420px; }} }}
  @media (max-width:480px) {{ .stats-row {{ grid-template-columns:1fr 1fr; }} .resources-grid {{ grid-template-columns:1fr; }} .topbar-right .btn-outline {{ display:none; }} }}
  .pl-toggle {{ cursor:pointer; user-select:none; }}
  .pl-toggle .pl-expand-arrow {{ display:inline-block; transition:transform 0.2s; font-size:11px; margin-left:6px; color:var(--text-light); }}
  .pl-toggle.open .pl-expand-arrow {{ transform:rotate(90deg); }}
  .pl-summary {{ font-size:12px; color:var(--text-light); margin-top:-8px; margin-bottom:4px; }}
  .pl-toggle.open + .pl-summary {{ display:none; }}
  .pl-detail {{ display:none; }}
  .pl-toggle.open ~ .pl-detail {{ display:block; }}
  .pl-flow {{ display:flex; gap:0; align-items:stretch; margin-bottom:12px; overflow-x:auto; padding-bottom:4px; }}
  .pl-phase {{ flex:1; min-width:110px; background:white; border:1px solid var(--border); padding:14px 12px; }}
  .pl-phase:first-child {{ border-radius:10px 0 0 10px; }}
  .pl-phase:last-of-type {{ border-radius:0 10px 10px 0; }}
  .pl-phase-name {{ font-size:12px; font-weight:600; color:var(--green); margin-bottom:8px; line-height:1.3; }}
  .pl-phase-trigger {{ font-size:10px; color:var(--text-light); line-height:1.4; }}
  .pl-phase-trigger strong {{ color:var(--text-mid); font-weight:500; }}
  .pl-arrow {{ display:flex; align-items:center; font-size:16px; color:var(--copper); padding:0 2px; flex-shrink:0; }}
  .pl-wf-tag {{ display:inline-block; font-size:9px; background:var(--green-pale); color:var(--green); padding:1px 6px; border-radius:8px; margin-top:4px; white-space:nowrap; margin-right:2px; }}
  @media (max-width:768px) {{ .pl-flow {{ flex-direction:column; gap:8px; }} .pl-phase {{ border-radius:10px !important; }} .pl-arrow {{ justify-content:center; transform:rotate(90deg); padding:4px 0; }} }}

  .bk-sched-header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:10px; }}
  .bk-avail-tag {{ font-size:11px; color:var(--text-light); background:var(--cream); border:1px solid var(--border); padding:3px 10px; border-radius:12px; }}
  .bk-rules {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:10px; margin-bottom:16px; }}
  .bk-rule {{ background:var(--green-pale); border-radius:8px; padding:10px 12px; }}
  .bk-rule-label {{ font-size:9px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:3px; }}
  .bk-rule-value {{ font-size:12px; color:var(--text); font-weight:500; word-break:break-word; overflow-wrap:anywhere; }}
  .bk-svc-grid {{ display:flex; flex-direction:column; gap:16px; }}
  .bk-svc-group {{ display:flex; gap:12px; align-items:stretch; }}
  .bk-dur-card {{ border:1px solid var(--border); border-radius:10px; padding:16px; display:flex; flex-direction:column; justify-content:center; align-items:center; min-width:100px; text-align:center; }}
  .bk-svc-card {{ border:1px solid var(--border); border-radius:10px; padding:18px; }}
  .bk-svc-name {{ font-size:14px; font-weight:600; color:var(--text); margin-bottom:10px; }}
  .bk-svc-price {{ font-size:16px; font-weight:600; color:var(--copper); margin-bottom:4px; }}
  .bk-svc-row {{ display:flex; gap:8px; margin-bottom:6px; font-size:12px; }}
  .bk-svc-label {{ color:var(--text-light); min-width:85px; flex-shrink:0; }}
  .bk-svc-value {{ color:var(--text-mid); }}
  .bk-detail-toggle {{ font-size:11px; color:var(--copper); cursor:pointer; margin-top:8px; display:inline-block; }}
  .bk-detail-toggle:hover {{ text-decoration:underline; }}
  .bk-q-list {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .bk-q-pill {{ font-size:10px; background:var(--copper-pale); color:var(--copper); padding:2px 8px; border-radius:8px; }}
  .action-item {{ display:flex; align-items:flex-start; gap:10px; padding:8px 0; font-size:13px; color:var(--text-mid); cursor:pointer; line-height:1.5; }}
  .action-item input[type="checkbox"] {{ margin-top:3px; accent-color:var(--copper); cursor:pointer; flex-shrink:0; }}
  .action-item input:checked + span {{ text-decoration:line-through; color:var(--text-light); }}
  @media (max-width:768px) {{ .bk-svc-group {{ flex-direction:column; }} .bk-dur-card {{ min-width:unset; }} .bk-rules {{ grid-template-columns:1fr 1fr; }} }}

  .ov-quicklinks {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }}
  .ov-link-card {{ display:flex; align-items:center; gap:8px; padding:12px 18px; background:white; border:1px solid var(--border); border-radius:10px; cursor:pointer; transition:all 0.15s; text-decoration:none; color:var(--text); }}
  .ov-link-card:hover {{ border-color:var(--copper); background:var(--copper-pale); }}
  .ov-link-icon {{ font-size:18px; flex-shrink:0; }}
  .ov-link-label {{ font-size:13px; font-weight:500; white-space:nowrap; }}

  .cn-label {{ font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); display:block; margin-bottom:6px; font-weight:500; }}
  .cn-input {{ width:100%; border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream); }}
  .cn-input:focus {{ border-color:var(--copper); }}
  .cn-checklist-wrap {{ border:1px solid var(--border); border-radius:8px; padding:10px; background:var(--cream); }}
  .cn-checklist {{ max-height:200px; overflow-y:auto; display:flex; flex-direction:column; gap:4px; }}
  .cn-item {{ display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:6px; cursor:pointer; font-size:12.5px; color:var(--text-mid); transition:background 0.1s; }}
  .cn-item:hover {{ background:var(--green-pale); }}
  .cn-item input {{ accent-color:var(--copper); cursor:pointer; }}
  .cn-item-cat {{ font-size:9px; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-light); background:var(--green-pale); padding:1px 6px; border-radius:6px; flex-shrink:0; }}
  .cn-item.hidden {{ display:none; }}

  .tm-row {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .tm-member {{ display:flex; align-items:center; gap:6px; padding:6px 12px; background:var(--green-pale); border-radius:8px; }}
  .tm-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
  .tm-name {{ font-size:12.5px; color:var(--text); font-weight:500; }}

  .sn-card {{ background:var(--green-pale); border:1px solid var(--border); }}
  .sn-list {{ list-style:none; display:flex; flex-direction:column; gap:8px; }}
  .sn-item {{ font-size:13px; color:var(--text-mid); display:flex; gap:8px; align-items:flex-start; line-height:1.6; }}
  .sn-icon {{ color:var(--green); flex-shrink:0; font-size:12px; margin-top:3px; }}

  .at-list {{ display:flex; flex-direction:column; gap:6px; }}
  .at-item {{ display:flex; gap:8px; align-items:flex-start; font-size:12.5px; color:var(--text-mid); line-height:1.5; padding:6px 10px; background:var(--cream); border-radius:6px; }}
  .at-bullet {{ color:var(--copper); flex-shrink:0; font-size:11px; margin-top:1px; }}
  .at-subgroup {{ margin-bottom:16px; }}
  .at-subgroup:last-child {{ margin-bottom:0; }}
  .at-subgroup-label {{ font-size:12px; font-weight:600; color:var(--text); margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid var(--border); }}
  .at-toggle {{ cursor:pointer; user-select:none; }}
  .at-toggle .at-arrow {{ display:inline-block; transition:transform 0.2s; font-size:11px; margin-left:6px; color:var(--text-light); }}
  .at-toggle.open .at-arrow {{ transform:rotate(90deg); }}
  .at-body {{ display:none; }}
  .at-toggle.open + .at-body {{ display:block; }}

  {journey_css}
</style>
</head>
<body>

<!-- WELCOME MODAL -->
<div class="pw-overlay" id="welcomeModal" style="display:none; background:rgba(30,51,41,0.92); backdrop-filter:blur(8px);">
  <div class="pw-box" style="max-width:480px; gap:0; text-align:center;">
    <div style="font-size:36px; margin-bottom:16px;">📸</div>
    <div class="pw-logo">Welcome to your</div>
    <div class="pw-client" style="margin-bottom:12px;">{esc(name)} Portal</div>
    <div style="width:40px; height:2px; background:var(--copper); border-radius:2px; margin:0 auto 24px;"></div>
    <p style="font-size:13.5px; color:rgba(255,255,255,0.65); line-height:1.7; margin-bottom:28px;">Everything Nicole built for you; in one place.</p>
    <div style="display:flex; flex-direction:column; gap:10px; width:100%; margin-bottom:32px; text-align:left;">
      <div style="display:flex; align-items:flex-start; gap:12px; background:rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px;"><span style="font-size:16px; flex-shrink:0;">◈</span><div><div style="font-size:13px; font-weight:600; color:white; margin-bottom:2px;">Overview</div><div style="font-size:12px; color:rgba(255,255,255,0.45);">Your account stats, quick tips, and at-a-glance summary</div></div></div>
      <div style="display:flex; align-items:flex-start; gap:12px; background:rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px;"><span style="font-size:16px; flex-shrink:0;">{'🗺️' if journey_branches else '⟳'}</span><div><div style="font-size:13px; font-weight:600; color:white; margin-bottom:2px;">{'Client Experience' if journey_branches else 'Workflows &amp; Automation'}</div><div style="font-size:12px; color:rgba(255,255,255,0.45);">{'Your complete client journey from inquiry to delivery' if journey_branches else 'Every workflow Nicole built; with step-by-step breakdowns'}</div></div></div>
      <div style="display:flex; align-items:flex-start; gap:12px; background:rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px;"><span style="font-size:16px; flex-shrink:0;">🎥</span><div><div style="font-size:13px; font-weight:600; color:white; margin-bottom:2px;">Zoom Recordings</div><div style="font-size:12px; color:rgba(255,255,255,0.45);">All your session recordings and notes in one place</div></div></div>
      <div style="display:flex; align-items:flex-start; gap:12px; background:rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px;"><span style="font-size:16px; flex-shrink:0;">🤖</span><div><div style="font-size:13px; font-weight:600; color:white; margin-bottom:2px;">Ask Robot Nicole</div><div style="font-size:12px; color:rgba(255,255,255,0.45);">Your AI assistant trained on your exact 17hats setup; 24/7</div></div></div>
    </div>
    <button class="pw-btn" onclick="dismissWelcome()" style="margin-bottom:0;">Let's go! →</button>
  </div>
</div>

<!-- PASSWORD OVERLAY -->
<div class="pw-overlay" id="pwOverlay">
  <div class="pw-box">
    <div class="pw-lock">🔒</div>
    <div class="pw-logo">A Portal by let Nicole help</div>
    <div class="pw-client">{esc(name)}</div>
    <div class="pw-subtitle">Client Portal</div>
    <div class="pw-label">Enter your portal password</div>
    <input type="password" class="pw-input" id="pwInput" placeholder="••••••••" onkeydown="if(event.key==='Enter')checkPassword()">
    <button class="pw-btn" onclick="checkPassword()">Enter Portal →</button>
    <div class="pw-error" id="pwError"></div>
    <div class="pw-footer">letnicolehelp.com</div>
  </div>
</div>

<button class="hamburger" id="hamburger" onclick="toggleMobileMenu()" aria-label="Menu"><span></span><span></span><span></span></button>
<div class="mobile-overlay" id="mobileOverlay" onclick="closeMobileMenu()"></div>

<aside class="sidebar">
  <div class="sidebar-logo">
    <div class="by-nicole">A Portal by let Nicole help</div>
    <div class="client-name">{esc(name)}</div>
    <div class="portal-label">Client Portal · {esc(setup_year)}</div>
  </div>
  <div class="sidebar-section">
    <div class="sidebar-section-label">Your Setup</div>
    <a class="nav-item active" onclick="showSection('overview')"><span class="icon">◈</span> Overview</a>
{journey_nav}
{workflows_nav}
    <a class="nav-item" onclick="showSection('pipelines')"><span class="icon">◫</span> Pipelines</a>
    <a class="nav-item" onclick="showSection('automations')"><span class="icon">⚙️</span> Automations</a>
{bookings_nav}
  </div>
  <div class="sidebar-section">
    <div class="sidebar-section-label">Resources</div>
    <a class="nav-item" onclick="showSection('zoom-recordings')"><span class="icon">🎥</span> Zoom Sessions<span class="action-badge" id="actionBadge" style="display:none;"></span></a>
    <a class="nav-item" id="nav-whats-new" onclick="showSection('whats-new')"><span class="icon">✦</span> What's New from Nicole<span class="nav-badge" id="newsBadge" style="display:none;"></span></a>
    <a class="nav-item" onclick="showSection('resources')"><span class="icon">⊞</span> Resource Library</a>
  </div>
  <div class="sidebar-section">
    <div class="sidebar-section-label">Support</div>
    <a class="nav-item" onclick="showSection('ask-robot-nicole')"><span class="icon">🤖</span> Ask Robot Nicole</a>
    <a class="nav-item" onclick="showSection('contact-nicole')"><span class="icon">✏️</span> Contact Nicole</a>
  </div>
  <div class="sidebar-footer">
    <p>Set up by Nicole · {esc(setup_month_year)}<br>
    <span id="lastUpdatedLine" style="color:rgba(255,255,255,0.2); font-size:10px;"></span><br>
    <a href="https://letnicolehelp.com" target="_blank">letnicolehelp.com</a></p>
  </div>
</aside>

<main class="main">
  <div class="topbar">
    <div class="topbar-left">
      {logo_topbar}
      <span class="tag-pill">17hats · Active</span>
    </div>
    <div class="topbar-right">
      <a href="#" class="btn btn-outline" onclick="printSection(); return false;">🖨️ Save as PDF</a>
      <a href="#" class="btn btn-outline" onclick="showSection('contact-nicole'); return false;">✏️ Contact Nicole</a>
      <a href="#" class="btn btn-copper" onclick="showSection('ask-robot-nicole')">🤖 Ask Robot Nicole</a>
    </div>
  </div>

  <section class="page-section active" id="overview">
    <div class="accent-banner"><div>
      <h2>Welcome back, {esc(name)} ✨</h2>
      <p>Everything Nicole set up for you: your workflows, resources &amp; AI assistant...all in one place.</p>
    </div></div>
    <div class="stats-row">
      <div class="stat-card" style="cursor:pointer;" onclick="showSection('{('client-experience' if journey_branches else 'workflows')}')"><div class="stat-label">Workflows Built</div><div class="stat-value">{num_wf}</div></div>
      <div class="stat-card" style="cursor:pointer;" onclick="showSection('pipelines')"><div class="stat-label">Pipelines Built</div><div class="stat-value">{num_pl}</div></div>
      <div class="stat-card" style="cursor:pointer;" onclick="showSection('automations')"><div class="stat-label">Automations</div><div class="stat-value">{num_auto}</div></div>
      {'<div class="stat-card" style="cursor:pointer;" onclick="showSection(\'bookings\')"><div class="stat-label">Booking Schedules</div><div class="stat-value">' + str(len(booking_schedules)) + '</div></div>' if has_bookings else ''}
    </div>
    <div class="two-col">
      <div class="card">
        <div class="card-title">📋 Your Account at a Glance</div>
        <p style="font-size:13.5px; color:var(--text-mid); line-height:1.7;">{esc(overview)}</p>{team_html}
        <div style="display:flex; align-items:center; gap:10px; margin-top:16px; padding:10px 14px; background:var(--copper-pale); border-radius:8px;">
          <span style="font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:var(--copper); font-weight:500; white-space:nowrap;">Recommended tune-up</span>
          <span style="font-size:13px; color:var(--text); font-weight:500;" id="reviewStatus">{esc(checkin_label)}</span>
        </div>
        <div style="margin-top:14px;">
        <a class="btn btn-outline" onclick="showSection('{('client-experience' if journey_branches else 'workflows')}')" style="font-size:12px;">{'Explore client experience →' if journey_branches else 'View all workflows →'}</a>
        </div>
      </div>
      <div class="card">
        <div class="card-title">⚡ Quick Tips for Your Setup</div>
        <ul style="list-style:none; display:flex; flex-direction:column; gap:10px;">
{tips_html}
        </ul>
      </div>
    </div>
{special_notes_card}
  </section>

{journey_section}

  <section class="page-section" id="workflows">
    <div class="section-header">
      <h1>Workflows &amp; Automation</h1>
      <p>Every workflow Nicole built for your 17hats account. Click any item to see how it works.</p>
    </div>
{workflows_html}
  </section>

  <section class="page-section" id="pipelines">
    <div class="section-header">
      <h1>Pipelines</h1>
      <p>What moves clients between phases and which workflows trigger those movements.</p>
    </div>
{pipelines_html}
  </section>

  <section class="page-section" id="automations">
    <div class="section-header">
      <h1>Automations</h1>
      <p>Everything running automatically in the background of your 17hats account.</p>
    </div>
{auto_html}
  </section>

{bookings_section}

  <section class="page-section" id="updates">
    <div class="section-header">
      <h1>Recommended Updates</h1>
      <p>As your business grows, your 17hats system should grow with it. Here's what Nicole recommends revisiting.</p>
    </div>
    <div class="update-timeline">
      <div class="update-item">
        <div class="update-timing">3 months in · {month3.strftime('%B %Y')}</div>
        <div class="update-title">Review your email templates</div>
        <div class="update-desc">After a few months of using your automated emails, review the language and tone. Your voice may have evolved, and you may want to tweak the wording based on how clients respond.</div>
      </div>
      <div class="update-item">
        <div class="update-timing">6 months in · {esc(format_month_year(checkin_date))}</div>
        <div class="update-title">Recommended tune-up</div>
        <div class="update-desc">At the 6-month mark, Nicole recommends a quick check-in to make sure your workflows still match how you're operating. New event types, team changes, or pricing updates may warrant adjustments.</div>
      </div>
      <div class="update-item">
        <div class="update-timing">12 months · {month12.strftime('%B %Y')}</div>
        <div class="update-title">Full system audit</div>
        <div class="update-desc">At the one-year mark, it's worth doing a complete review; active pipelines, automation sequences, unused tags, and new 17hats features. Nicole offers a 1-hour Audit service for this.</div>
      </div>
      <div class="update-item">
        <div class="update-timing">Ongoing</div>
        <div class="update-title">New 17hats features</div>
        <div class="update-desc">17hats releases updates regularly. Nicole covers new features on YouTube as they drop; check the "What's New" section of this portal to stay up to date.</div>
      </div>
    </div>
  </section>

  <section class="page-section" id="zoom-recordings">
    <div class="section-header">
      <h1>Zoom Sessions</h1>
      <p>All your session recordings with Nicole in one place: watch, rewatch, and reference anytime.</p>
    </div>
{sessions_html}
    <div class="card" style="border:1px dashed var(--border); background:var(--cream);">
      <div style="text-align:center; padding:20px 0;">
        <div style="font-size:28px; margin-bottom:10px;">🎥</div>
        <div style="font-size:14px; font-weight:500; color:var(--text-mid); margin-bottom:6px;">More recordings will appear here</div>
        <div style="font-size:12.5px; color:var(--text-light);">Nicole adds new sessions as they're completed.</div>
      </div>
    </div>
  </section>

  <section class="page-section" id="whats-new">
    <div class="section-header"><h1>What's New from Nicole</h1><p>Latest posts, videos, and tips; all relevant to your 17hats setup.</p></div>
    <div class="card" id="announcements-card" style="display:none;"><div class="card-title">✨ From Nicole</div><div id="announcements-list" style="display:flex; flex-direction:column; gap:12px;"></div></div>
    <div class="card">
      <div class="card-title">📹 Latest YouTube Videos</div>
      <div style="margin-bottom:14px;"><iframe src="https://www.youtube.com/embed/videoseries?list=PLpfpFiNP9vG4dosv5VjAlmvMc9GjF0j7B&rel=0" style="width:100%; height:360px; border:none; border-radius:10px;" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
      <a href="https://youtube.com/@letnicolehelp" target="_blank" class="btn btn-outline" style="font-size:12px;">View all on YouTube →</a>
    </div>
    <div class="card">
      <div class="card-title">✍️ Latest from Nicole's Blog</div>
      <div id="blog-loading" style="text-align:center; padding:30px; color:var(--text-light); font-size:13px;">Loading latest posts...</div>
      <div class="content-grid" id="blog-grid" style="display:none;"></div>
      <div id="blog-error" style="display:none; text-align:center; padding:20px;"><p style="font-size:13px; color:var(--text-light); margin-bottom:12px;">Couldn't load posts automatically.</p><a href="https://www.letnicolehelp.com/blog" target="_blank" class="btn btn-outline">View Blog →</a></div>
    </div>
  </section>

  <section class="page-section" id="resources">
    <div class="section-header"><h1>Resource Library</h1><p>Tools, links, and references hand-picked for your setup.</p></div>
    <div class="resources-grid">
      <a href="https://help.17hats.com" target="_blank" class="resource-card"><div class="resource-icon">📚</div><div class="resource-title">17hats Help Center</div><div class="resource-desc">Official documentation for any feature or question about your account.</div></a>
      <a href="https://letnicolehelp.com" target="_blank" class="resource-card"><div class="resource-icon">🌐</div><div class="resource-title">letnicolehelp.com</div><div class="resource-desc">Blog posts, guides, and services from Nicole; your ongoing 17hats resource.</div></a>
      <a href="https://youtube.com/@letnicolehelp" target="_blank" class="resource-card"><div class="resource-icon">▶</div><div class="resource-title">Nicole's YouTube Channel</div><div class="resource-desc">How-to videos, 17hats walkthroughs, and feature deep dives.</div></a>
      <a href="#" class="resource-card" onclick="showSection('ask-robot-nicole')"><div class="resource-icon">◎</div><div class="resource-title">Ask Robot Nicole</div><div class="resource-desc">Robot Nicole is trained on your 17hats setup. Ask it anything, anytime.</div></a>
      <a href="https://instagram.com/letnicolehelp" target="_blank" class="resource-card"><div class="resource-icon">📱</div><div class="resource-title">@letnicolehelp on Instagram</div><div class="resource-desc">Quick 17hats tips, reels, and behind-the-scenes from Nicole.</div></a>
      <a href="https://letnicolehelp.17hats.com/p#/scheduling/ktcgccxcfptwkcbrhgzsvkdzsgpcxntx/s/61821" target="_blank" class="resource-card"><div class="resource-icon">📅</div><div class="resource-title">Book a Tech Check</div><div class="resource-desc">Ready for an update? Book a call with Nicole.</div></a>
    </div>
  </section>

  <section class="page-section" id="ask-robot-nicole">
    <div class="section-header"><h1>Ask Robot Nicole</h1><p>Robot Nicole knows your {esc(name)} 17hats setup. Ask it anything; workflows, automations, how Nicole configured something, 17hats how-tos.</p></div>
    <div class="chat-wrapper">
      <div class="chat-header"><div class="chat-avatar">◎</div><div class="chat-header-info"><h3>Claude · {esc(name)} Assistant</h3><p>Trained on your 17hats setup by Nicole · letnicolehelp.com</p></div></div>
      <div class="chat-messages" id="chatMessages">
        <div class="message assistant"><div class="message-avatar assistant-avatar">◎</div><div class="message-bubble">Hi! I'm Robot Nicole, configured specifically for <strong>{esc(name)}'s</strong> 17hats setup. I know how Nicole built your workflows, automations and pipelines. Ask me anything!</div></div>
      </div>
      <div class="chat-input-area">
        <textarea class="chat-input" id="chatInput" placeholder="Ask about your 17hats setup..." rows="1" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
        <button class="chat-send" id="sendBtn" onclick="sendMessage()">➤</button>
      </div>
    </div>
  </section>

  <section class="page-section" id="contact-nicole">
    <div class="section-header"><h1>Contact Nicole</h1><p>Questions, change requests, or just need to reach out. Nicole typically responds within 1-2 business days.</p></div>
    <div class="two-col">
      <div class="card"><div class="card-title">📅 Book a Session</div><p style="font-size:13.5px; color:var(--text-mid); line-height:1.7; margin-bottom:20px;">Your setup includes two 1-hour walkthrough Tech Check calls, but additional call packs are always available!</p><a href="https://letnicolehelp.17hats.com/p#/lcf/xnngshvxghfzwsnxzpvzbndcxxsfwndb" target="_blank" class="btn btn-copper">Book a Tech Check Call →</a></div>
      <div class="card" style="border-left:3px solid var(--copper);"><div class="card-title">💡 Good to know</div><p style="font-size:13.5px; color:var(--text-mid); line-height:1.7;">Not sure if your request is a quick fix or something bigger? Ask Robot Nicole first. Minor updates to existing workflows are typically included in your annual maintenance. New workflows, pipelines, or event types are quoted separately.</p></div>
    </div>
    <div class="card">
      <div class="card-title">✏️ Send Nicole a Message</div>
      <div style="display:flex; flex-direction:column; gap:14px;">
        <div><label class="cn-label">What's this about? *</label><input type="text" id="cn-subject" placeholder="e.g. Update my headshot booking workflow" class="cn-input"></div>
        <div><label class="cn-label">Details *</label><textarea id="cn-details" rows="4" placeholder="Describe what you need changed, added, or your question..." class="cn-input" style="resize:vertical;"></textarea></div>
        <div><label class="cn-label">Urgency</label><select id="cn-urgency" class="cn-input"><option value="Normal">Normal — no rush</option><option value="High">High — needed soon</option><option value="Low">Low — whenever you get to it</option></select></div>
        <div>
          <label class="cn-label">Which parts of your setup? <span style="font-weight:400; text-transform:none; letter-spacing:0; font-size:11px; color:var(--text-light);">(optional — select any that apply)</span></label>
          <div class="cn-checklist-wrap">
            <input type="text" id="cn-search" placeholder="Search workflows, pipelines, bookings..." class="cn-input" style="margin-bottom:8px;" oninput="filterSetupItems(this.value)">
            <div class="cn-checklist" id="cn-checklist"></div>
          </div>
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <button class="btn btn-copper" onclick="contactNicole('email')">📧 Open in email →</button>
          <button class="btn btn-outline" onclick="contactNicole('copy')">📋 Copy to clipboard</button>
          <span id="cn-status" style="font-size:12px; color:var(--green); display:none;"></span>
        </div>
      </div>
    </div>
  </section>
</main>

<script>
const PORTAL_PASSWORD='{password}';
const PORTAL_LAST_UPDATED='{today}';
const WHATS_NEW_UPDATED='{today_iso}';
const CLIENT_KEY='{client_key}';

function checkPassword(){{const i=document.getElementById('pwInput');if(i.value===PORTAL_PASSWORD){{document.getElementById('pwOverlay').classList.add('unlocked');setTimeout(()=>{{document.getElementById('pwOverlay').style.display='none';const w=localStorage.getItem(CLIENT_KEY+'_welcomed');if(!w){{document.getElementById('welcomeModal').style.display='flex';localStorage.setItem(CLIENT_KEY+'_welcomed','1');}}}},500);initPortal();}}else{{i.classList.add('shake');document.getElementById('pwError').textContent='Incorrect password. Try again.';setTimeout(()=>i.classList.remove('shake'),400);}}}}
function dismissWelcome(){{const m=document.getElementById('welcomeModal');if(m){{m.classList.add('unlocked');setTimeout(()=>m.style.display='none',500);}}}}
function initPortal(){{const e=document.getElementById('lastUpdatedLine');if(e)e.textContent='Last updated: '+PORTAL_LAST_UPDATED;const l=localStorage.getItem(CLIENT_KEY+'_news_seen');const b=document.getElementById('newsBadge');if(b&&(!l||new Date(l)<new Date(WHATS_NEW_UPDATED)))b.style.display='inline-block';}}

(function(){{
  const setupDate=new Date('{setup_date or "2026-01-01"}');
  const checkInDate=new Date('{checkin_date or "2026-07-01"}');
  const now=new Date();
  const ageEl=document.getElementById('acctAge');
  const statusEl=document.getElementById('reviewStatus');
  if(!ageEl||!statusEl)return;
  const days=Math.floor((now-setupDate)/(1000*60*60*24));
  const months=Math.floor(days/30);
  if(days<30)ageEl.textContent='New!';
  else if(months<12)ageEl.textContent=months+' mo';
  else{{const y=Math.floor(months/12);const m=months%12;ageEl.textContent=y+'yr'+(m>0?' '+m+'mo':'');}}
  if(now>=checkInDate){{statusEl.textContent='Tune-up review due ✦';statusEl.style.color='var(--copper)';}}
  else{{const d=Math.ceil((checkInDate-now)/(1000*60*60*24));statusEl.textContent='Tune-up in '+d+' days';statusEl.style.color='var(--text-light)';}}
}})();

function showSection(id){{document.querySelectorAll('.page-section').forEach(s=>s.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));const m=document.querySelector('.nav-item[onclick*="'+id+'"]');if(m)m.classList.add('active');window.scrollTo(0,0);if(id==='whats-new'){{const b=document.getElementById('newsBadge');if(b)b.style.display='none';}}closeMobileMenu();}}
function toggleWorkflow(h){{const b=h.nextElementSibling;const t=h.querySelector('.workflow-toggle');b.classList.toggle('open');t.classList.toggle('open');}}
function saveCheckbox(cb){{const key='portal_'+cb.id;if(cb.checked)localStorage.setItem(key,'1');else localStorage.removeItem(key);updateActionBadge();}}
function updateActionBadge(){{const all=document.querySelectorAll('.action-item input[type="checkbox"]');const unchecked=Array.from(all).filter(function(cb){{return !cb.checked;}}).length;const badge=document.getElementById('actionBadge');if(badge){{if(unchecked>0){{badge.textContent=unchecked;badge.style.display='inline-flex';}}else{{badge.style.display='none';}}}}}}
(function(){{document.querySelectorAll('.action-item input[type="checkbox"]').forEach(function(cb){{if(localStorage.getItem('portal_'+cb.id)==='1')cb.checked=true;}});updateActionBadge();}})();
{journey_js}
function toggleMobileMenu(){{document.querySelector('.sidebar').classList.toggle('mobile-open');document.getElementById('hamburger').classList.toggle('open');document.getElementById('mobileOverlay').classList.toggle('visible');}}
function closeMobileMenu(){{document.querySelector('.sidebar').classList.remove('mobile-open');document.getElementById('hamburger').classList.remove('open');document.getElementById('mobileOverlay').classList.remove('visible');}}
function printSection(){{window.print();}}
const SETUP_ITEMS={setup_items_js};
(function(){{const c=document.getElementById('cn-checklist');if(!c)return;SETUP_ITEMS.forEach(function(it,i){{const d=document.createElement('label');d.className='cn-item';d.setAttribute('data-name',it.name.toLowerCase());d.innerHTML='<input type="checkbox" value="'+i+'"><span class="cn-item-cat">'+it.cat+'</span><span>'+it.name+'</span>';c.appendChild(d);}});}})();
function filterSetupItems(q){{const lc=q.toLowerCase();document.querySelectorAll('.cn-item').forEach(function(el){{if(!lc||el.getAttribute('data-name').indexOf(lc)!==-1)el.classList.remove('hidden');else el.classList.add('hidden');}});}}
function contactNicole(mode){{const subj=document.getElementById('cn-subject').value.trim();const details=document.getElementById('cn-details').value.trim();const urgency=document.getElementById('cn-urgency').value;const st=document.getElementById('cn-status');if(!subj||!details){{st.style.display='inline';st.style.color='#c0392b';st.textContent='Please fill in the subject and details.';return;}}const checked=[];document.querySelectorAll('#cn-checklist input:checked').forEach(function(cb){{checked.push(SETUP_ITEMS[parseInt(cb.value)].name);}});let body='MESSAGE FROM: '+PORTAL_CLIENT_NAME+'\\n\\nSubject: '+subj+'\\n\\nDetails:\\n'+details+'\\n\\nUrgency: '+urgency;if(checked.length)body+='\\n\\nSetup items referenced:\\n- '+checked.join('\\n- ');body+='\\n\\n---\\nSent from '+PORTAL_CLIENT_NAME+' client portal';if(mode==='email'){{window.location.href='mailto:nicole@letnicolehelp.com?subject='+encodeURIComponent(subj+' ('+PORTAL_CLIENT_NAME+')')+'&body='+encodeURIComponent(body);st.style.display='inline';st.style.color='var(--green)';st.textContent='Email client opened!';}}else{{navigator.clipboard.writeText(body).then(function(){{st.style.display='inline';st.style.color='var(--green)';st.textContent='Copied to clipboard!';setTimeout(function(){{st.style.display='none';}},3000);}});}}}}
document.querySelectorAll('.nav-item').forEach(i=>i.addEventListener('click',function(){{document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));this.classList.add('active');}}));

const CLIENT_CONTEXT=`{client_context_js}`;

const PROXY_URL='https://robot-nicole-proxy.letnicolehelp.workers.dev/';
const PORTAL_INDUSTRY='{industry}';
let chatHistory=[];

async function sendMessage(){{const input=document.getElementById('chatInput');const btn=document.getElementById('sendBtn');const messages=document.getElementById('chatMessages');const text=input.value.trim();if(!text)return;appendMessage('user',text);chatHistory.push({{role:'user',content:text}});input.value='';input.style.height='auto';btn.disabled=true;const thinking=document.createElement('div');thinking.className='message assistant';thinking.innerHTML='<div class="message-avatar assistant-avatar">◎</div><div class="message-bubble"><div class="thinking"><span></span><span></span><span></span></div></div>';messages.appendChild(thinking);messages.scrollTop=messages.scrollHeight;try{{const response=await fetch(PROXY_URL,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{model:'claude-sonnet-4-20250514',max_tokens:1000,system:CLIENT_CONTEXT,messages:chatHistory,client_key:CLIENT_KEY}})}});const data=await response.json();const reply=data.content?.[0]?.text||"Sorry, I couldn't get a response. Try again!";chatHistory.push({{role:'assistant',content:reply}});thinking.remove();appendMessage('assistant',reply);}}catch(err){{thinking.remove();appendMessage('assistant',"Hmm, something went wrong. Please try again in a moment.");}}btn.disabled=false;messages.scrollTop=messages.scrollHeight;}}
function appendMessage(role,text){{const messages=document.getElementById('chatMessages');const div=document.createElement('div');div.className='message '+role;const ac=role==='assistant'?'◎':'✦';const cls=role==='assistant'?'assistant-avatar':'user-avatar';div.innerHTML='<div class="message-avatar '+cls+'">'+ac+'</div><div class="message-bubble">'+text.replace(/\\n/g,'<br>').replace(/\\*\\*(.*?)\\*\\*/g,'<strong>$1</strong>')+'</div>';messages.appendChild(div);messages.scrollTop=messages.scrollHeight;}}
function autoResize(el){{el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px';}}
function handleKey(e){{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();sendMessage();}}}}

async function loadBlogPosts(){{const g=document.getElementById('blog-grid');const l=document.getElementById('blog-loading');const e=document.getElementById('blog-error');try{{const r=await fetch(PROXY_URL,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{action:'blog_posts',limit:4}})}});const d=await r.json();if(!d.posts||d.posts.length===0)throw new Error('No posts');g.innerHTML=d.posts.map((p,i)=>{{let t='';if(p.media?.wixMedia?.image?.url)t=p.media.wixMedia.image.url;else if(p.media?.embedMedia?.thumbnail?.url)t=p.media.embedMedia.thumbnail.url;const ts=t?"background-image:url('"+t+"');background-size:cover;background-position:center;":"background:linear-gradient(135deg,#1a3d30 0%,#2d5246 100%);";const ex=p.excerpt?p.excerpt.substring(0,100)+(p.excerpt.length>100?'...':''):'';const u=p.url?p.url.base+p.url.path:'https://www.letnicolehelp.com/blog';return'<a href="'+u+'" target="_blank" class="content-card"><div class="content-card-thumb yt-thumb" style="'+ts+'">'+(t?'':'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:28px;opacity:0.4;">✦</div>')+'</div><div class="content-card-body"><div class="content-card-type">From Nicole\\'s Blog'+(i===0?' · New':'')+'</div><div class="content-card-title">'+p.title+'</div>'+(ex?'<div style="font-size:11.5px;color:var(--text-light);margin-top:4px;line-height:1.5;">'+ex+'</div>':'')+'</div></a>';}}).join('');l.style.display='none';g.style.display='grid';}}catch(err){{l.style.display='none';e.style.display='block';}}}}
loadBlogPosts();

async function loadAnnouncements(){{const l=document.getElementById('announcements-list');const c=document.getElementById('announcements-card');try{{const r=await fetch('https://lnh-gh.github.io/robot-nicole-client-portal/announcements.json?nocache='+Date.now());const d=await r.json();const f=d.filter(i=>!i.industry||i.industry.length===0||i.industry.includes('General')||i.industry.includes(PORTAL_INDUSTRY));if(!f.length)return;l.innerHTML=f.map(i=>{{const lb=i.label?'<div style="font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:var(--copper);margin-bottom:3px;">'+i.label+'</div>':'';return'<a href="'+(i.url||'#')+'" target="_blank" style="display:flex;gap:14px;align-items:flex-start;text-decoration:none;padding:12px;border-radius:8px;border:1px solid var(--border);"><span style="font-size:22px;flex-shrink:0;">'+(i.emoji||'✦')+'</span><div>'+lb+'<div style="font-size:13.5px;font-weight:500;color:var(--text);margin-bottom:3px;">'+i.title+'</div><div style="font-size:12.5px;color:var(--text-light);line-height:1.5;">'+(i.desc||'')+'</div></div></a>';}}).join('');c.style.display='block';}}catch(e){{}}}}
loadAnnouncements();

const PORTAL_CLIENT_NAME='{esc(name)}';
</script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(portal_html)

    print(f"✅ Portal generated: {output_path}")
    print(f"   Client: {name}")
    print(f"   Workflows: {len(all_wf)}")
    print(f"   Automation groups: {len(auto_groups)}")
    print(f"   Booking schedules: {len(booking_schedules)}")
    print(f"   Sessions: {sum(1 for i in range(1,4) if d.get(f'Session {i} Topic'))}")
    print(f"   File size: {len(portal_html):,} chars")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 generate_portal.py data.json output.html")
        sys.exit(1)
    generate_portal(sys.argv[1], sys.argv[2])
