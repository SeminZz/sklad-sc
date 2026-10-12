// Корзины на странице «Склад».
// Двойной клик по детали → окно «Поиск покупателя» → выбрать или создать → деталь в корзине покупателя.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const money = v => (v == null ? '—' : Number(v).toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  let carts = [];          // открытые корзины текущего пользователя
  let activeId = null;     // выбранная вкладка
  let pendingPart = null;  // деталь, которую сейчас добавляем
  let selectedCustomer = null;
  let found = [];
  let options = null;

  // ---------- запросы ----------
  function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  async function api(url, body) {
    const opts = body === undefined
      ? {headers: {Accept: 'application/json'}}
      : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf(), Accept: 'application/json'},
         body: JSON.stringify(body)};
    const resp = await fetch(url, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) { const err = new Error(data.error || 'Ошибка ' + resp.status); err.data = data; throw err; }
    return data;
  }
  const cartUrl = (id, action) => SALES.cartUrl.replace('/0/', '/' + id + '/') + action + '/';

  let toastTimer;
  function toast(text, kind) {
    const t = $('toast');
    t.textContent = text;
    t.className = 'toast' + (kind ? ' ' + kind : '');
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, kind === 'warn' ? 7000 : 3500);
  }

  // ---------- панель корзин ----------
  function render() {
    const tabs = $('cart-tabs');
    tabs.innerHTML = '';
    if (!carts.length) {
      tabs.innerHTML = '<span class="cart-empty-hint">Корзин пока нет. Дважды щёлкните по детали, чтобы добавить её покупателю.</span>';
      $('cart-body').hidden = true;
      return;
    }
    if (!carts.some(c => c.id === activeId)) activeId = carts[carts.length - 1].id;
    carts.forEach(c => {
      const tab = document.createElement('div');
      tab.className = 'cart-tab' + (c.id === activeId ? ' active' : '');
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'cart-tab-name';
      b.textContent = `${c.customer.name} (${c.items.length})`;
      b.onclick = () => { activeId = c.id; render(); };
      const x = document.createElement('button');
      x.type = 'button';
      x.className = 'cart-tab-x';
      x.title = 'Закрыть корзину';
      x.textContent = '×';
      x.onclick = () => closeCart(c);
      tab.append(b, x);
      tabs.appendChild(tab);
    });

    const cart = carts.find(c => c.id === activeId);
    $('cart-body').hidden = false;
    const cu = cart.customer;
    $('cart-customer').innerHTML =
      `<b>${esc(cu.name)}</b><span>${esc(cu.phone)}</span><span>${esc(cu.email)}</span>` +
      (cu.discount ? `<span class="pill">скидка ${cu.discount}%</span>` : '');
    $('cart-items').innerHTML = cart.items.length ? cart.items.map(i => `
      <tr>
        <td class="barcode">${esc(i.barcode)}</td><td>${esc(i.category)}</td><td>${esc(i.brand)}</td>
        <td>${esc(i.car_model)}</td><td>${esc(i.generation)}</td><td>${esc(i.year || '')}</td>
        <td>${esc(i.warehouse)}</td><td>${esc(i.cell)}</td><td class="num">${money(i.price)}</td>
        <td><button type="button" class="row-x" data-item="${i.id}" title="Убрать из корзины">×</button></td>
      </tr>`).join('') : '<tr><td colspan="10" class="muted">Корзина пуста</td></tr>';
    $('cart-total').textContent = money(cart.total);
    $('cart-total-discount').textContent =
      cu.discount ? `Со скидкой ${cu.discount}%: ${money(cart.total_with_discount)}` : '';
  }

  function upsert(cart) {
    const i = carts.findIndex(c => c.id === cart.id);
    if (i >= 0) carts[i] = cart; else carts.push(cart);
    activeId = cart.id;
    render();
  }

  // Закрыть вкладку. Если в корзине что-то есть, нужен второй щелчок по ×.
  let confirmCloseId = null;
  async function closeCart(c) {
    if (c.items.length && confirmCloseId !== c.id) {
      confirmCloseId = c.id;
      toast(`В корзине ${c.items.length} шт. Нажмите × ещё раз, чтобы закрыть корзину «${c.customer.name}».`, 'warn');
      setTimeout(() => { if (confirmCloseId === c.id) confirmCloseId = null; }, 4000);
      return;
    }
    confirmCloseId = null;
    try {
      await api(cartUrl(c.id, 'close'), {});
      carts = carts.filter(x => x.id !== c.id);
      render();
    } catch (e) { toast(e.message, 'error'); }
  }

  $('cart-items').addEventListener('click', async e => {
    const btn = e.target.closest('.row-x');
    if (!btn) return;
    try { upsert((await api(cartUrl(activeId, 'remove'), {item_id: Number(btn.dataset.item)})).cart); }
    catch (err) { toast(err.message, 'error'); }
  });
  $('cart-clear').addEventListener('click', async () => {
    try { upsert((await api(cartUrl(activeId, 'clear'), {})).cart); toast('Корзина очищена'); }
    catch (err) { toast(err.message, 'error'); }
  });

  // ---------- добавление ----------
  async function addToCart(target) {
    try {
      const data = await api(SALES.addUrl, Object.assign({part_id: pendingPart.id}, target));
      upsert(data.cart);
      $('dlg-customer').close();
      $('dlg-create').close();
      toast(data.added ? `${pendingPart.barcode} добавлена: ${data.cart.customer.name}`
                       : `${pendingPart.barcode} уже была в этой корзине`);
      if (data.warning) setTimeout(() => toast(data.warning, 'warn'), 600);
    } catch (e) { toast(e.message, 'error'); }
  }

  // ---------- окно «Поиск покупателя» ----------
  function partLabel(p) {
    return [p.barcode, p.category, p.brand, p.car_model, p.generation].filter(Boolean).join(' · ') +
      (p.price != null ? ` — ${money(p.price)} ₽` : '');
  }

  function openSearch(part) {
    pendingPart = part;
    selectedCustomer = null;
    found = [];
    $('dlg-customer-part').textContent = 'Деталь: ' + partLabel(part);
    const current = carts.find(c => c.id === activeId);
    const toCurrent = $('customer-to-current');
    toCurrent.hidden = !current;
    if (current) toCurrent.textContent = `В текущую корзину: ${current.customer.name}`;
    $('customer-q').value = '';
    renderFound();
    $('dlg-customer').showModal();
    $('customer-q').focus();
  }

  function renderFound() {
    $('customer-results').innerHTML = found.map((c, i) => `
      <tr data-i="${i}" class="${selectedCustomer && selectedCustomer.id === c.id ? 'sel' : ''}" tabindex="0">
        <td>${esc(c.name)}</td><td>${esc(c.kind)}</td><td>${esc(c.phone)}</td><td>${esc(c.email)}</td>
        <td>${esc(c.address)}</td><td>${esc(c.created)}</td><td class="num">${c.discount ? c.discount + '%' : ''}</td>
      </tr>`).join('');
    $('customer-count').textContent = found.length;
    const q = $('customer-q').value.trim();
    $('customer-note').textContent = !q ? 'Начните вводить телефон или фамилию.'
      : (found.length ? '' : 'Никого не нашли. Нажмите «Создать покупателя».');
    $('customer-pick').disabled = !selectedCustomer;
  }

  let searchTimer, searchNo = 0;
  $('customer-q').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      const q = $('customer-q').value.trim();
      const my = ++searchNo;
      if (!q) { found = []; selectedCustomer = null; renderFound(); return; }
      try {
        const data = await api(SALES.customersUrl + '?q=' + encodeURIComponent(q));
        if (my !== searchNo) return;
        found = data.customers;
        selectedCustomer = found.length === 1 ? found[0] : null;
        renderFound();
      } catch (e) { toast(e.message, 'error'); }
    }, 250);
  });
  $('customer-q').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); if (selectedCustomer) addToCart({customer_id: selectedCustomer.id}); }
  });
  $('customer-results').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-i]');
    if (!tr) return;
    selectedCustomer = found[Number(tr.dataset.i)];
    renderFound();
  });
  $('customer-results').addEventListener('dblclick', e => {
    const tr = e.target.closest('tr[data-i]');
    if (tr) addToCart({customer_id: found[Number(tr.dataset.i)].id});
  });
  $('customer-pick').addEventListener('click', () => selectedCustomer && addToCart({customer_id: selectedCustomer.id}));
  $('customer-to-current').addEventListener('click', () => addToCart({cart_id: activeId}));
  $('customer-new').addEventListener('click', openCreate);

  // ---------- окно «Создание покупателя» ----------
  function fillSelect(sel, items, empty) {
    sel.innerHTML = (empty !== undefined ? `<option value="">${esc(empty)}</option>` : '') +
      items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
  }

  function toggleCompany() {
    const isPerson = $('cf-kind').value === 'person';
    document.querySelectorAll('#customer-form .company').forEach(el => { el.hidden = isPerson; });
  }
  $('cf-kind').addEventListener('change', toggleCompany);

  async function openCreate() {
    if (!options) {
      try { options = await api(SALES.optionsUrl); } catch (e) { toast(e.message, 'error'); return; }
      fillSelect($('cf-kind'), options.kinds);
      fillSelect($('cf-gender'), options.genders, '—');
      fillSelect($('cf-manager'), options.managers, '—');
    }
    const form = $('customer-form');
    form.reset();
    $('cf-manager').value = String(options.current_user);
    $('cf-errors').hidden = true;
    form.querySelectorAll('.invalid').forEach(el => el.classList.remove('invalid'));
    // Подставить то, что уже ввели в поиске: телефон или ФИО
    const q = $('customer-q').value.trim();
    if (q) {
      if (/^[\d\s()+\-.]+$/.test(q)) $('cf-phone').value = q;
      else {
        const [last, first, middle] = q.split(/\s+/);
        $('cf-last_name').value = last || '';
        $('cf-first_name').value = first || '';
        $('cf-middle_name').value = middle || '';
      }
    }
    toggleCompany();
    $('dlg-create').showModal();
    (q && /^[\d\s()+\-.]+$/.test(q) ? $('cf-last_name') : $('cf-phone')).focus();
  }

  $('cf-cancel').addEventListener('click', () => $('dlg-create').close());

  $('customer-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const body = Object.fromEntries(new FormData(form).entries());
    if (body.kind === 'person') { body.company_name = ''; body.inn = ''; }
    form.querySelectorAll('.invalid').forEach(el => el.classList.remove('invalid'));
    try {
      const data = await api(SALES.createUrl, body);
      toast('Покупатель создан: ' + data.customer.name);
      await addToCart({customer_id: data.customer.id});
    } catch (err) {
      const errors = (err.data && err.data.errors) || {};
      const lines = [];
      Object.entries(errors).forEach(([field, msgs]) => {
        const input = $('cf-' + field);
        if (input) input.classList.add('invalid');
        lines.push(msgs.join(' '));
      });
      $('cf-errors').textContent = lines.join(' ') || err.message;
      $('cf-errors').hidden = false;
    }
  });

  // ---------- запуск ----------
  window.Cart = {addPart: openSearch};
  api(SALES.cartsUrl).then(d => { carts = d.carts; render(); }).catch(() => {});
})();
