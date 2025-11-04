// Dashboard UI helper JS
// Responsibilities: fetch cog list, render cards, call enable/disable endpoints
async function ajax(url, opts={}){
  const res = await fetch(url, opts);
  if(!res.ok){
    const txt = await res.text().catch(()=>null);
    throw new Error(`HTTP ${res.status}: ${txt||res.statusText}`);
  }
  const ct = res.headers.get('content-type')||'';
  if(ct.includes('application/json')) return res.json();
  return res.text();
}

// Theme application helper — exposed globally so templates can call it.
window.applyTheme = function(name){
  try{
    const root = document.documentElement.style;
    if(name === 'green'){
      root.setProperty('--accent','#10b981'); root.setProperty('--accent-2','#16a34a');
    }else if(name === 'blue'){
      root.setProperty('--accent','#3b82f6'); root.setProperty('--accent-2','#06b6d4');
    }else if(name === 'amber'){
      root.setProperty('--accent','#f59e0b'); root.setProperty('--accent-2','#d97706');
    }
  }catch(e){ /* ignore */ }
};

function createCard(name){
  const tpl = document.getElementById('cog-card-tpl');
  const el = tpl.content.cloneNode(true);
  const root = el.querySelector('.card');
  const pretty = name.replace(/[-_]/g,' ').replace(/\b\w/g, c=>c.toUpperCase());
  // keep icon slot, set label text
  const nameEl = root.querySelector('.cog-name');
  if(nameEl){
    const label = nameEl.querySelector('.label');
    if(label) label.textContent = pretty;
    else nameEl.textContent = pretty;
  }
  const descEl = root.querySelector('.cog-desc');
  if(descEl) descEl.textContent = root.dataset.description || '';
  const badge = root.querySelector('.cog-badge');
  const enableBtn = root.querySelector('.enable');
  const disableBtn = root.querySelector('[data-action="disable"]');
  const reloadBtn = root.querySelector('[data-action="reload"]');
  const detailsLink = root.querySelector('[data-action="details"]');
  enableBtn.addEventListener('click', () => handleAction(name, 'enable', root, badge));
  disableBtn.addEventListener('click', () => handleAction(name, 'disable', root, badge));
  if(reloadBtn) reloadBtn.addEventListener('click', ()=> handleAction(name, 'reload', root));
  if(detailsLink) detailsLink.href = '/cogs/' + encodeURIComponent(name);
  return root;
}

async function handleAction(name, op, root){
  const apiKey = window.__CHRONIX_API_KEY || null;
  const url = `/cogs/${encodeURIComponent(name)}/${op}`;
  const headers = apiKey ? {'X-API-Key': apiKey} : {};
  try{
    root.classList.add('working');
    const res = await ajax(url, {method:'POST', headers});
    // Visual confirmation and status badge update
    const badge = root.querySelector('.cog-badge');
    if(op === 'enable'){
      if(badge){ badge.textContent = 'Enabled'; badge.classList.add('on'); badge.classList.remove('off'); }
    }else if(op === 'disable'){
      if(badge){ badge.textContent = 'Disabled'; badge.classList.add('off'); badge.classList.remove('on'); }
    }
    root.classList.remove('working');
    root.classList.add('success');
    setTimeout(()=>root.classList.remove('success'), 2000);
    return res;
  }catch(e){
    root.classList.remove('working');
    const err = document.createElement('div'); err.className='note'; err.textContent = 'Operation failed: '+e.message;
    root.appendChild(err);
  }
}

async function initCogs(listUrl, enableUrlTemplate, disableUrlTemplate){
  try{
    const data = await ajax(listUrl);
    const list = data.cogs||[];
    const status = await ajax('/cogs/status').catch(()=>({status:{}}));
    const st = status.status || {};
    const container = document.getElementById('cog-list');
    container.innerHTML = '';
    // try to fetch meta for nicer titles/descriptions
    const meta = await ajax('/cogs/meta').catch(()=>({meta:{}}));
    const m = meta.meta || {};
    list.sort().forEach(name=>{
      const card = createCard(name);
      const badge = card.querySelector('.cog-badge');
      const enabled = !!st[name];
      if(badge) { badge.textContent = enabled ? 'Enabled' : 'Disabled'; badge.classList.toggle('on', enabled); badge.classList.toggle('off', !enabled); }
      // set title/description if provided
      const cfg = m[name] || {};
      if(cfg.title){ card.querySelector('.cog-name').textContent = cfg.title; }
      if(cfg.description){ card.querySelector('.cog-desc').textContent = cfg.description; }
      container.appendChild(card);
    });
  }catch(e){
    console.error('Failed to load cogs', e);
    document.getElementById('cogs-root').innerHTML = '<p class="lead">Failed to load cogs. Check logs.</p>';
  }
}

// expose for inline init
window.initCogs = initCogs;

// Sidebar behaviour: toggles collapsed state and persists to localStorage
function initSidebar(){
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  if(!toggle || !sidebar) return;
  const COLLAPSED_KEY = 'chronix.sidebar.collapsed';
  const setCollapsed = (v)=>{
    sidebar.classList.toggle('collapsed', !!v);
    try{ localStorage.setItem(COLLAPSED_KEY, !!v ? '1' : '0'); }catch(e){}
  };
  // restore state
  try{ setCollapsed(localStorage.getItem(COLLAPSED_KEY) === '1'); }catch(e){}
  toggle.addEventListener('click', ()=>{
    setCollapsed(!sidebar.classList.contains('collapsed'));
  });

  // highlight active link
  try{
    const path = location.pathname.replace(/\/$/, '') || '/';
    const links = sidebar.querySelectorAll('a');
    links.forEach(a=>{
      const href = a.getAttribute('href') || '/';
      if(href === path) a.classList.add('active');
    });
  }catch(e){}
}

window.initSidebar = initSidebar;

// Global page init: wire common buttons (index cards, instance controls, theme)
document.addEventListener('DOMContentLoaded', async ()=>{
  // apply stored theme
  try{ const saved = localStorage.getItem('chronix.theme'); if(saved && window.applyTheme) window.applyTheme(saved); }catch(e){}
  try{ const mode = localStorage.getItem('chronix.theme_mode') || 'dark'; if(mode === 'light') document.documentElement.classList.add('theme-light'); else document.documentElement.classList.remove('theme-light'); }catch(e){}
  // if no saved theme, fetch server settings for default_theme
  try{
    if(!localStorage.getItem('chronix.theme')){
      const res = await fetch('/settings');
      if(res.ok){ const j = await res.json(); const s = j.settings || {}; if(s.default_theme && window.applyTheme) window.applyTheme(s.default_theme); }
    }
  }catch(e){}

  // index page buttons
  document.querySelectorAll('[data-action="open-cogs"]').forEach(b=>b.addEventListener('click', ()=>{ window.location = '/cogs/ui'; }));
  document.querySelectorAll('[data-action="open-configs"]').forEach(b=>b.addEventListener('click', ()=>{ window.location = '/configs/ui'; }));
  ['start','stop','restart'].forEach(op=>{
    document.querySelectorAll('[data-action="'+op+'"]').forEach(b=>b.addEventListener('click', async ()=>{
      b.classList.add('working');
      try{
        await ajax('/instance/'+op, {method:'POST'});
        b.classList.remove('working');
        b.classList.add('success');
        setTimeout(()=>b.classList.remove('success'),1500);
      }catch(e){ b.classList.remove('working'); alert('Action failed: '+e.message); }
    }));
  });
});

// Pending actions polling
window.updatePendingActions = async function(){
  try{
    const res = await ajax('/actions/pending');
    const n = res.pending || 0;
    const el = document.getElementById('pending-count'); if(el) el.textContent = String(n);
  }catch(e){/* ignore */}
  try{ setTimeout(()=>{ if(window.updatePendingActions) window.updatePendingActions(); }, 8000); }catch(e){}
};

// expose RPC port if provided by the server (read from /settings on load)
document.addEventListener('DOMContentLoaded', async ()=>{
  try{
    const res = await fetch('/settings'); if(res.ok){ const j = await res.json(); const s = j.settings || {}; if(s.rpc_port) window.__CHRONIX_RPC_PORT = String(s.rpc_port); }
  }catch(e){}
});
