/** =====================  CONFIG  ===================== **/
const API_BASE = '';
const API_CREATE_JOB = '/api/fusion/jobs/create';
const API_SEARCH_CUSTOMERS = '/api/fusion/customers/search';
const BOARD = 'AnswringAgent Afterhours';
const PASTE = 'Unassigned Technician';
const FALLBACK_RAG_URL = '/mapping/';

/** =====================  UTIL  ===================== **/
const $ = (q)=>document.querySelector(q);
const $$ = (q)=>Array.from(document.querySelectorAll(q));
const show = (el,yes=true)=>{ el.style.display = yes ? '' : 'none'; }
const toast = (msg, ok=true)=>{ const t=$('#toast'); t.textContent=msg; t.className=`toast show ${ok?'ok':'err'}`; setTimeout(()=>t.classList.remove('show'),3200); }
$('#today').textContent = new Date().toLocaleDateString();
const progress = $('#progress');
const startProgress = ()=>{ progress.classList.add('show'); };
const endProgress = ()=>{ progress.classList.remove('show'); };

/** =====================  PAGE LOADER  ===================== **/
window.addEventListener('load', ()=> {
  $('#pageLoader').classList.add('hide');
});

/** =====================  REVEAL ON SCROLL  ===================== **/
const io = new IntersectionObserver((entries)=>{ entries.forEach(e=>{ if(e.isIntersecting) e.target.classList.add('in'); }); },{threshold:.08});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

/** =====================  SIDEBAR NAV  ===================== **/
$('#navAnswering').onclick = (e)=>{ e.preventDefault(); window.scrollTo({top:0,behavior:'smooth'}); toast('Answering Service Agent', true); };
$('#navIntegration').onclick = (e)=>{ e.preventDefault(); window.location.href = '/mapping/'; };
$('#navFsm').onclick = (e)=>{ e.preventDefault(); toast('Field Service Management — coming soon', true); };
$('#navWarranty').onclick = (e)=>{ e.preventDefault(); toast('Warranty Processing — coming soon', true); };
$('#navStatus').onclick = (e)=>{ e.preventDefault(); window.location.href = '/'; };
$('#logoutBtn').onclick = ()=>{ toast('Signed out (demo)'); setTimeout(()=>history.back(),600); };

/** =====================  TABS  ===================== **/
$('#tabExisting').onclick = ()=>{
  $('#tabExisting').classList.add('active'); $('#tabNew').classList.remove('active');
  show($('#panelExisting'),true); show($('#panelNew'),false);
  window.scrollTo({top:0,behavior:'smooth'});
};
$('#tabNew').onclick = ()=>{
  $('#tabNew').classList.add('active'); $('#tabExisting').classList.remove('active');
  show($('#panelExisting'),false); show($('#panelNew'),true);
  window.scrollTo({top:0,behavior:'smooth'});
};

/** =====================  WIZARDS  ===================== **/
function makeWizard(rootSel){
  const panes = $$(rootSel + ' .pane');
  let step = 0;
  const setStep = (i)=>{
    step = Math.max(0, Math.min(panes.length-1, i));
    panes.forEach((p,idx)=>{
      p.classList.toggle('active', idx===step);
      p.style.transform = idx<step ? 'translateX(-12%)' : (idx>step ? 'translateX(12%)' : 'translateX(0)');
    });
  };
  const validateStep = ()=>{
    const req = panes[step].querySelectorAll('[required]');
    for(const el of req){
      if(!el.value.trim()){ el.focus(); el.reportValidity?.(); toast('Please fill the required fields.', false); return false; }
    }
    return true;
  };
  panes.forEach(p=>{
    p.querySelectorAll('[data-next]').forEach(b=> b.addEventListener('click', ()=>{ if(validateStep()) setStep(step+1); }));
    p.querySelectorAll('[data-prev]').forEach(b=> b.addEventListener('click', ()=> setStep(step-1)));
  });
  setStep(0);
  return { setStep, validateStep };
}
const jobWizard  = makeWizard('#panelExisting #jobPanes');
const custWizard = makeWizard('#panelNew #custPanes');

/** =====================  MODAL (Result / Downloads)  ===================== **/
const modal = $('#resultModal');
const linkList = $('#linkList');
const emailBadge = $('#emailBadge');
const openDocBtn = $('#openDocBtn');
$('#closeModal').onclick = ()=> modal.classList.remove('show');

function setEmailBadge(status){
  emailBadge.textContent = `Email: ${status || 'unknown'}`;
  emailBadge.classList.remove('ok','warn');
  if(status === 'sent') emailBadge.classList.add('ok'); else emailBadge.classList.add('warn');
}
function showResult({email_status, links={}, rag_url}){
  setEmailBadge(email_status);
  linkList.innerHTML='';
  const items=[];
  if(links.docx) items.push({href:links.docx,label:'Download DOCX'});
  if(rag_url) items.push({href:rag_url,label:'Open RAG HTML'});
  if(links.json) items.push({href:links.json,label:'View JSON'});
  if(!items.length) items.push({href:FALLBACK_RAG_URL,label:'Open Mapping (fallback)'});

  for(const it of items){
    const a=document.createElement('a'); a.href=it.href; a.target='_blank'; a.rel='noopener';
    a.innerHTML=`<span class="i"></span>${it.label}`; linkList.appendChild(a);
  }
  openDocBtn.onclick = ()=> window.open(items[0].href,'_blank','noopener');
  modal.classList.add('show');

  if(links.docx){
    const a = document.createElement('a');
    a.href = links.docx;
    a.download = '';
    a.target = '_blank';
    a.rel = 'noopener';
    a.style.display='none';
    document.body.appendChild(a);
    setTimeout(()=>{ a.click(); a.remove(); }, 0);
  }
}

/** =====================  API HELPERS  ===================== **/
async function postJSON(url, payload){
  const r = await fetch(url,{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const data = await r.json().catch(()=> ({}));
  if(!r.ok){
    const msg = data?.response?.message || data?.message || data?.error || 'Service Fusion error';
    const code = data?.status_code || r.status;
    throw new Error(`${msg} — HTTP ${code} (${data?.path || url})`);
  }
  return data;
}

async function getJSON(url){
  const r = await fetch(url);
  const data = await r.json().catch(()=> ({}));
  if(!r.ok) throw new Error(data.error || data.message || `HTTP ${r.status}`);
  return data;
}

/** =====================  CUSTOMER SEARCH  ===================== **/
let searchTimeout;
let selectedCustomer = null;

async function searchCustomers(query) {
  if (!query || query.length < 2) return [];
  try {
    const data = await getJSON(`${API_BASE}${API_SEARCH_CUSTOMERS}?q=${encodeURIComponent(query)}`);
    return Array.isArray(data) ? data : (data.customers || []);
  } catch (err) {
    console.error('Customer search failed:', err);
    return [];
  }
}

function showSuggestions(customers) {
  const container = $('#customer_suggestions');
  if (!customers.length) {
    container.style.display = 'none';
    return;
  }
  
  container.innerHTML = customers.map(customer => `
    <div class="suggestion-item" data-customer='${JSON.stringify(customer)}'>
      <div class="suggestion-name">${customer.name || customer.customer_name || 'Unknown'}</div>
      <div class="suggestion-details">ID: ${customer.id || customer.customer_id || 'N/A'} | ${customer.city || ''} ${customer.state || ''}</div>
    </div>
  `).join('');
  
  container.style.display = 'block';
  
  // Add click handlers
  container.querySelectorAll('.suggestion-item').forEach(item => {
    item.addEventListener('click', () => selectCustomer(JSON.parse(item.dataset.customer)));
  });
}

function selectCustomer(customer) {
  selectedCustomer = customer;
  
  // Fill customer fields
  $('#customer_name').value = customer.name || customer.customer_name || '';
  $('#customer_id').value = customer.id || customer.customer_id || '';
  $('#customer_search').value = customer.name || customer.customer_name || '';
  
  // Auto-fill location if available
  if (customer.locations && customer.locations.length > 0) {
    const location = customer.locations[0];
    $('#location_name').value = location.name || '';
    $('#street_1').value = location.address || location.street_1 || '';
    $('#city').value = location.city || '';
    $('#state').value = location.state || location.state_prov || '';
    $('#zip').value = location.zip || location.postal_code || '';
  }
  
  // Auto-fill contact if available
  if (customer.contacts && customer.contacts.length > 0) {
    const contact = customer.contacts[0];
    $('#contact_name').value = contact.name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim();
    $('#contact_phone').value = contact.phone || '';
    $('#contact_email').value = contact.email || '';
  }
  
  // Hide suggestions
  $('#customer_suggestions').style.display = 'none';
  
  toast(`Customer "${customer.name || customer.customer_name}" selected`, true);
}

// Customer search event handlers
$('#customer_search').addEventListener('input', (e) => {
  const query = e.target.value.trim();
  
  clearTimeout(searchTimeout);
  if (query.length < 2) {
    $('#customer_suggestions').style.display = 'none';
   return;
  }
  
  searchTimeout = setTimeout(async () => {
    const customers = await searchCustomers(query);
    showSuggestions(customers);
  }, 300);
});

// Hide suggestions when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('#customer_search') && !e.target.closest('#customer_suggestions')) {
    $('#customer_suggestions').style.display = 'none';
  }
});

/** =====================  EXISTING JOB SUBMIT  ===================== **/
const btn = $('#btnCreate');
$('#jobForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  if(!jobWizard.validateStep()) return;
  if(btn.disabled) return;
  btn.disabled=true; btn.textContent='Creating…';
  startProgress();

  const payload = {
    customer_id: $('#customer_id').value.trim() || null,
    customer_name: $('#customer_name').value.trim(),
    service_location: {
      name: $('#location_name').value.trim(),
      address: $('#street_1').value.trim() || null,
      city: $('#city').value.trim() || null,
      state: $('#state').value.trim() || null,
      zip: $('#zip').value.trim() || null
    },
    category: $('#category').value,
    priority: $('#priority').value,
    problem_summary: `${$('#category').value || 'General'} • ${$('#priority').value || 'Normal'}`,
    problem_details: $('#description').value.trim(),
    contact: {
      name: $('#contact_name').value.trim() || null,
      phone: $('#contact_phone').value.trim() || null,
      email: $('#contact_email').value.trim() || null
    },
    preferred_window: { start: $('#win_start').value || null, end: $('#win_end').value || null },
    service_fusion: { board: BOARD, paste_to: PASTE },
    email: { to: $('#shared_email').value.trim() || null }
  };

  try{
    const data = await postJSON(`${API_BASE}${API_CREATE_JOB}`, payload);
    toast(`Job ${data.job_id || 'created'}`, true);
    showResult({ email_status: data.email_status, links: data.links||{}, rag_url: data.rag_url });
    e.target.reset(); jobWizard.setStep(0);
  }catch(err){
    console.error(err); toast(err.message || 'Request failed', false);
    showResult({ email_status: 'unknown', links:{}, rag_url: FALLBACK_RAG_URL });
  }finally{
    btn.disabled=false; btn.textContent='Create Job';
    endProgress();
  }
});

/** =====================  NEW CUSTOMER SUBMIT (Demo)  ===================== **/
$('#newCustomerForm').addEventListener('submit',(e)=>{
  e.preventDefault();
  if(!custWizard.validateStep()) return;

  const name = $('#nc_name').value.trim();
  const custId = `CUST-${Math.random().toString(36).slice(2,7).toUpperCase()}`;

  $('#customer_name').value = name || '';
  $('#customer_id').value = custId;
  $('#location_name').value = $('#loc_name').value || '';
  $('#street_1').value = $('#loc_street').value || '';
  $('#city').value = $('#loc_city').value || '';
  $('#state').value = $('#loc_state').value || '';
  $('#zip').value = $('#loc_zip').value || '';

  toast(`Customer ${custId} created`, true);
  $('#tabExisting').click();
  setTimeout(()=> $('#customer_name').focus(), 150);
});


