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

def build_auto_group(name, count, desc, items_raw):
    """Build one expandable automation group."""
    items = parse_steps(items_raw) if isinstance(items_raw, str) else items_raw
    return f'''        <div class="workflow-item">
          <div class="workflow-header" onclick="toggleWorkflow(this)">
            <div class="workflow-header-left">
              <div class="workflow-dot"></div>
              <span class="workflow-name">{esc(name)}</span>
              <span class="workflow-tag">{count} automations</span>
            </div>
            <span class="workflow-toggle">▾</span>
          </div>
          <div class="workflow-body">
            <p>{esc(desc)}</p>
            <ul class="workflow-steps">
{build_step_li(items)}
            </ul>
          </div>
        </div>'''

def build_detail_row(label, value):
    """Build a copper-label / value detail row."""
    return f'''            <div style="display:flex; gap:10px; font-size:13px; color:var(--text-mid); line-height:1.5;">
              <span style="color:var(--copper); font-weight:500; white-space:nowrap; min-width:160px;">{esc(label)}</span>
              <span style="color:var(--text-light); font-style:italic;">{esc(value)}</span>
            </div>'''

def build_booking_service(name, details):
    """Build one expandable booking service item."""
    rows = '\n'.join([build_detail_row(k, v) for k, v in details])
    return f'''        <div class="workflow-item">
          <div class="workflow-header" onclick="toggleWorkflow(this)">
            <div class="workflow-header-left">
              <div class="workflow-dot"></div>
              <span class="workflow-name">{esc(name)}</span>
              <span class="workflow-tag">service</span>
            </div>
            <span class="workflow-toggle">▾</span>
          </div>
          <div class="workflow-body">
            <div style="display:flex; flex-direction:column; gap:8px;">
{rows}
            </div>
          </div>
        </div>'''

def build_booking_schedule(sched_name, sched_url, details, services):
    """Build one complete booking schedule card."""
    detail_rows = '\n'.join([build_detail_row(k, v) for k, v in details])
    service_items = '\n'.join([build_booking_service(n, d) for n, d in services])
    url_btn = f'''      <div style="margin-bottom:16px;">
        <a href="{esc(sched_url)}" target="_blank" class="btn btn-outline" style="font-size:12px;">Open Scheduling Page →</a>
      </div>''' if sched_url else ''

    return f'''    <div class="card">
      <div class="card-title">📅 {esc(sched_name)}</div>
{url_btn}
      <div style="background:var(--copper-pale); border-radius:8px; padding:16px 18px; margin-bottom:20px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--copper); margin-bottom:10px;">Schedule Details</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
{detail_rows}
        </div>
      </div>
      <div class="workflow-list">
{service_items}
      </div>
    </div>'''

def build_session_card(num, topic, date_str, url, notes_raw, passcode=''):
    """Build one zoom session card."""
    date_display = format_date_display(date_str)
    rec_btn = f'<a href="{esc(url)}" target="_blank" class="btn btn-copper" style="font-size:12px;">▶ Watch Recording</a>' if url else ''

    if notes_raw:
        note_lines = parse_steps(notes_raw)
        if passcode:
            note_lines.append(f'Passcode: {passcode}')
        notes_html = '\n'.join([
            f'          <li style="font-size:13px; color:var(--text-mid); display:flex; gap:10px;"><span style="color:var(--copper); flex-shrink:0;">✔️</span> {esc(n)}</li>'
            for n in note_lines
        ])
        notes_section = f'''      <div style="background:var(--green-pale); border-radius:8px; padding:16px 18px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:10px;">Session Notes</div>
        <ul style="list-style:none; display:flex; flex-direction:column; gap:8px;">
{notes_html}
        </ul>
      </div>'''
    else:
        notes_section = '''      <div style="background:var(--green-pale); border-radius:8px; padding:16px 18px;">
        <div style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); margin-bottom:10px;">Session Notes</div>
        <p style="font-size:13px; color:var(--text-light); font-style:italic;">Recording link and notes will be added after the session.</p>
      </div>'''

    return f'''    <div class="card">
      <div class="card-title">🎥 Session {num} · {esc(topic or "Untitled")}</div>
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
        <span style="font-size:12px; color:var(--text-light); letter-spacing:0.05em;">{esc(date_display or "Date TBD")}</span>
        {rec_btn}
      </div>
{notes_section}
    </div>'''

def build_pipeline_card(name, phases, image_url):
    """Build one pipeline card with optional image."""
    img = f'<img src="{esc(image_url)}" alt="{esc(name)} Pipeline" style="width:100%; border-radius:8px; border:1px solid var(--border);">' if image_url else '<div style="text-align:center; padding:30px; background:var(--green-pale); border-radius:8px; color:var(--text-light); font-size:13px;">Pipeline screenshot will be added here</div>'
    return f'''    <div class="card">
      <div class="card-title">🗂️ {esc(name)} Pipeline</div>
      <p style="font-size:13px; color:var(--text-light); margin-bottom:16px;">{esc(phases)} phases</p>
      {img}
    </div>'''


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

    for i in range(1, 5):
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
    num_auto = int(d.get('Num Automations', 0) or 0)

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

    # ── Build automations ──
    auto_html = ''
    auto_groups = []
    for label, field, desc in [
        ('Lead Capture', 'Automations - Lead Capture', 'These automations fire when a new lead submits the lead capture form.'),
        ('Pipeline Phase Movements', 'Automations - Pipelines', 'Automatic pipeline phase changes triggered by workflow actions and time-based rules.'),
        ('Workflow Automations', 'Automations - Workflows', 'Automated emails, tags, and workflow transitions within workflows.'),
        ('Document Automations', 'Automations - Documents', 'Document-related automations.'),
    ]:
        raw = d.get(field, '')
        if not raw or raw == 'TBD': continue
        items = parse_steps(raw)
        auto_html += build_auto_group(label, len(items), desc, items) + '\n'
        auto_groups.append((label, items))

    # ── Build pipelines ──
    pipelines_html = ''
    for i in range(1, 5):
        pname = d.get(f'Pipeline {i} Name', '')
        if not pname: continue
        pphases = d.get(f'Pipeline {i} Phases', '')
        pimg = d.get(f'Pipeline {i} Image URL', '')
        pipelines_html += build_pipeline_card(pname, pphases, pimg) + '\n'

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
        sessions_html += build_session_card(i, topic, sdate, surl, snotes) + '\n'

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
      <p>Your availability schedules and the services/sessions configured within each one.</p>
    </div>

{bookings_html}
  </section>
''' if has_bookings else ''

    # ── Recommended updates ──
    setup_d = datetime.strptime(setup_date[:10], '%Y-%m-%d') if setup_date else datetime.now()
    month3 = setup_d.replace(month=setup_d.month + 3) if setup_d.month <= 9 else setup_d.replace(year=setup_d.year + 1, month=setup_d.month - 9)
    month12 = setup_d.replace(year=setup_d.year + 1)

    # ── CLIENT_CONTEXT ──
    client_context = build_client_context(d, all_wf, auto_groups, booking_schedules)
    # Escape for JS string literal (backtick template)
    client_context_js = client_context.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

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
  .workflow-header {{ display:flex; align-items:center; justify-content:space-between; padding:14px 18px; cursor:pointer; background:var(--green-pale); transition:background 0.2s; }}
  .workflow-header:hover {{ background:#deeae4; }}
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
  @keyframes pulse-badge {{ 0%,100% {{ box-shadow:0 0 0 2px rgba(184,125,82,0.3); }} 50% {{ box-shadow:0 0 0 5px rgba(184,125,82,0); }} }}
  @media print {{ .sidebar,.hamburger,.mobile-overlay,.pw-overlay,#welcomeModal,.topbar-right {{ display:none !important; }} .main {{ margin-left:0 !important; }} .page-section {{ display:block !important; page-break-after:always; }} .workflow-body {{ display:block !important; }} body {{ background:white; }} .card {{ box-shadow:none; border:1px solid #ddd; }} }}
  @media (max-width:768px) {{ .sidebar {{ transform:translateX(-100%); transition:transform 0.3s ease; z-index:99; width:280px; }} .sidebar.mobile-open {{ transform:translateX(0); }} .hamburger {{ display:flex; }} .main {{ margin-left:0; }} .topbar {{ padding:14px 16px 14px 64px; }} .page-section {{ padding:24px 16px; }} .stats-row {{ grid-template-columns:1fr 1fr; gap:10px; }} .content-grid {{ grid-template-columns:1fr; }} .resources-grid {{ grid-template-columns:1fr 1fr; }} .two-col {{ grid-template-columns:1fr; }} .accent-banner {{ flex-direction:column; gap:16px; }} .accent-banner h2 {{ font-size:20px; }} .chat-wrapper {{ height:420px; }} }}
  @media (max-width:480px) {{ .stats-row {{ grid-template-columns:1fr 1fr; }} .resources-grid {{ grid-template-columns:1fr; }} .topbar-right .btn-outline {{ display:none; }} }}
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
      <div style="display:flex; align-items:flex-start; gap:12px; background:rgba(255,255,255,0.06); border-radius:10px; padding:12px 14px;"><span style="font-size:16px; flex-shrink:0;">⟳</span><div><div style="font-size:13px; font-weight:600; color:white; margin-bottom:2px;">Workflows &amp; Automation</div><div style="font-size:12px; color:rgba(255,255,255,0.45);">Every workflow Nicole built; with step-by-step breakdowns</div></div></div>
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
    <a class="nav-item" onclick="showSection('workflows')"><span class="icon">⟳</span> Workflows</a>
    <a class="nav-item" onclick="showSection('pipelines')"><span class="icon">◫</span> Pipelines</a>
    <a class="nav-item" onclick="showSection('automations')"><span class="icon">⚙️</span> Automations</a>
{bookings_nav}
  </div>
  <div class="sidebar-section">
    <div class="sidebar-section-label">Resources</div>
    <a class="nav-item" onclick="showSection('zoom-recordings')"><span class="icon">🎥</span> Zoom Sessions</a>
    <a class="nav-item" id="nav-whats-new" onclick="showSection('whats-new')"><span class="icon">✦</span> What's New from Nicole<span class="nav-badge" id="newsBadge" style="display:none;"></span></a>
    <a class="nav-item" onclick="showSection('resources')"><span class="icon">⊞</span> Resource Library</a>
  </div>
  <div class="sidebar-section">
    <div class="sidebar-section-label">Support</div>
    <a class="nav-item" onclick="showSection('ask-robot-nicole')"><span class="icon">🤖</span> Ask Robot Nicole</a>
    <a class="nav-item" onclick="showSection('requests')"><span class="icon">✏️</span> Request a Change</a>
    <a class="nav-item" onclick="showSection('get-help')"><span class="icon">◉</span> Get Help from Nicole</a>
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
      <a href="mailto:nicole@letnicolehelp.com" class="btn btn-outline">📧 Email Nicole</a>
      <a href="#" class="btn btn-copper" onclick="showSection('ask-robot-nicole')">🤖 Ask Robot Nicole</a>
    </div>
  </div>

  <section class="page-section active" id="overview">
    <div class="accent-banner"><div>
      <h2>Welcome back, {esc(name)} ✨</h2>
      <p>Everything Nicole set up for you: your workflows, resources &amp; AI assistant...all in one place.</p>
    </div></div>
    <div class="stats-row">
      <div class="stat-card"><div class="stat-label">Workflows Built</div><div class="stat-value">{num_wf}</div></div>
      <div class="stat-card"><div class="stat-label">Pipelines Built</div><div class="stat-value">{num_pl}</div></div>
      <div class="stat-card"><div class="stat-label">Automations</div><div class="stat-value">{num_auto}</div></div>
      <div class="stat-card"><div class="stat-label">Recommended tune-up</div><div class="stat-value">{esc(checkin_label)}</div></div>
    </div>
    <div class="two-col">
      <div class="card">
        <div class="card-title">📋 Your Account at a Glance</div>
        <p style="font-size:13.5px; color:var(--text-mid); line-height:1.7;">{esc(overview)}</p><br>
        <a class="btn btn-outline" onclick="showSection('workflows')" style="font-size:12px;">View all workflows →</a>
      </div>
      <div class="card">
        <div class="card-title">⚡ Quick Tips for Your Setup</div>
        <ul style="list-style:none; display:flex; flex-direction:column; gap:10px;">
{tips_html}
        </ul>
      </div>
    </div>
  </section>

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
      <p>Visual maps of your {esc(name)} pipelines; exactly how Nicole set them up in 17hats.</p>
    </div>
{pipelines_html}
  </section>

  <section class="page-section" id="automations">
    <div class="section-header">
      <h1>Automations</h1>
      <p>Everything running automatically in the background of your 17hats account. Click any group to see the details.</p>
    </div>
    <div class="card">
      <div class="card-title">⚙️ Automations Running in the Background</div>
      <div class="workflow-list">
{auto_html}
      </div>
    </div>
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

  <section class="page-section" id="get-help">
    <div class="section-header"><h1>Get Help from Nicole</h1><p>When you need more than your portal can offer; Nicole's here.</p></div>
    <div class="two-col">
      <div class="card"><div class="card-title">📅 Book a Session</div><p style="font-size:13.5px; color:var(--text-mid); line-height:1.7; margin-bottom:20px;">Your setup includes two 1-hour walkthrough Tech Check calls, but additional call packs are always available!</p><a href="https://letnicolehelp.17hats.com/p#/lcf/xnngshvxghfzwsnxzpvzbndcxxsfwndb" target="_blank" class="btn btn-copper">Book a Tech Check Call →</a></div>
      <div class="card"><div class="card-title">📧 Send Nicole a Message</div><p style="font-size:13.5px; color:var(--text-mid); line-height:1.7; margin-bottom:20px;">Have a question that Robot Nicole can't answer? Reach out directly. Nicole typically responds within 1-2 business days.</p>
        <div style="display:flex; flex-direction:column; gap:10px;">
          <input type="text" id="msgSubject" placeholder="Subject" style="border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream);">
          <textarea rows="4" id="msgBody" placeholder="Your question or request..." style="border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream); resize:none;"></textarea>
          <button class="btn btn-primary" style="align-self:flex-start;" onclick="openEmail()">Send Message →</button>
        </div>
      </div>
    </div>
    <div class="card" style="background:var(--green-pale);"><div class="card-title">💌 Stay in Nicole's World</div><div class="resources-grid" style="margin:0;">
      <a href="https://youtube.com/@letnicolehelp" target="_blank" class="resource-card"><div class="resource-icon">▶</div><div class="resource-title">YouTube</div></a>
      <a href="https://instagram.com/letnicolehelp" target="_blank" class="resource-card"><div class="resource-icon">📸</div><div class="resource-title">Instagram</div></a>
    </div></div>
  </section>

  <section class="page-section" id="requests">
    <div class="section-header"><h1>Request a Change</h1><p>Want to update something in your 17hats setup? Submit it here and Nicole will review it within 1-2 business days.</p></div>
    <div class="card" style="border-left:3px solid var(--copper);"><div class="card-title">💡 Before you submit</div><p style="font-size:13.5px; color:var(--text-mid); line-height:1.7;">Not sure if your request is a quick fix or something bigger? Ask Robot Nicole first; she can help you figure out what's involved before you submit. Minor updates to existing workflows are typically included in your annual maintenance. New workflows, pipelines, or event types are quoted separately.</p></div>
    <div class="card"><div class="card-title">✏️ Submit a Change Request</div>
      <div style="display:flex; flex-direction:column; gap:14px;">
        <div><label style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); display:block; margin-bottom:6px;">Request Summary *</label><input type="text" id="req-summary" placeholder="e.g. Add a new event type" style="width:100%; border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream);"></div>
        <div><label style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); display:block; margin-bottom:6px;">Full Details *</label><textarea id="req-detail" rows="4" placeholder="Describe exactly what you'd like changed or added..." style="width:100%; border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream); resize:vertical;"></textarea></div>
        <div><label style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); display:block; margin-bottom:6px;">Why / Context</label><textarea id="req-why" rows="2" placeholder="Why do you need this change?" style="width:100%; border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream); resize:vertical;"></textarea></div>
        <div><label style="font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:var(--text-light); display:block; margin-bottom:6px;">Urgency</label><select id="req-urgency" style="width:100%; border:1px solid var(--border); border-radius:7px; padding:10px 13px; font-family:'Montserrat',sans-serif; font-size:13px; outline:none; color:var(--text); background:var(--cream);"><option value="Normal">Normal; no rush</option><option value="High">High; needed soon</option><option value="Low">Low; whenever you get to it</option></select></div>
        <div><button class="btn btn-copper" onclick="submitRequest()">Submit Request →</button><div id="req-status" style="font-size:13px; margin-top:10px; display:none;"></div></div>
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
function toggleMobileMenu(){{document.querySelector('.sidebar').classList.toggle('mobile-open');document.getElementById('hamburger').classList.toggle('open');document.getElementById('mobileOverlay').classList.toggle('visible');}}
function closeMobileMenu(){{document.querySelector('.sidebar').classList.remove('mobile-open');document.getElementById('hamburger').classList.remove('open');document.getElementById('mobileOverlay').classList.remove('visible');}}
function printSection(){{window.print();}}
function openEmail(){{const s=document.getElementById('msgSubject').value.trim()||'Question about my 17hats setup';const b=document.getElementById('msgBody').value.trim()||'';window.location.href='mailto:nicole@letnicolehelp.com?subject='+encodeURIComponent(s)+'&body='+encodeURIComponent(b);}}
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
function submitRequest(){{const s=document.getElementById('req-summary').value.trim();const d=document.getElementById('req-detail').value.trim();const w=document.getElementById('req-why').value.trim();const u=document.getElementById('req-urgency').value;const st=document.getElementById('req-status');if(!s||!d){{st.style.display='block';st.style.color='#c0392b';st.textContent='Please fill in both the summary and details fields.';return;}}const subj='Portal Change Request: '+s+' ('+PORTAL_CLIENT_NAME+')';const body='CHANGE REQUEST FROM: '+PORTAL_CLIENT_NAME+'\\n\\nSummary: '+s+'\\n\\nDetails:\\n'+d+(w?'\\n\\nWhy / Context:\\n'+w:'')+'\\n\\nUrgency: '+u+'\\n\\n---\\nSent from '+PORTAL_CLIENT_NAME+' client portal';window.location.href='mailto:nicole@letnicolehelp.com?subject='+encodeURIComponent(subj)+'&body='+encodeURIComponent(body);st.style.display='block';st.style.color='var(--green)';st.textContent='Your email client should open with the request details. Send it and Nicole will follow up!';}}
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
