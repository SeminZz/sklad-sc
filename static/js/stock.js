// Страница «Склад»: фильтры сверху, таблица остатков с группировкой перетаскиванием.
(function () {
  'use strict';

  const form = document.getElementById('filters');
  const brandSel = document.getElementById('f-brand');
  const modelSel = document.getElementById('f-model');
  const groupChips = document.getElementById('group-chips');
  const groupAdd = document.getElementById('group-add');
  const groupPanel = document.getElementById('group-panel');

  let groupFields = [];

  // ---------- Модель доступна только после выбора марки ----------
  const brandModel = linkBrandModel(brandSel, modelSel, STOCK.modelsUrl);

  // ---------- Таблица ----------
  const money = {thousand: ' ', decimal: ',', symbol: '', precision: 2};

  const columns = [
    {title: 'Id', field: 'id', width: 80, hozAlign: 'right', sorter: 'number'},
    {title: 'Бирка', field: 'barcode', width: 115, cssClass: 'col-barcode', headerFilter: 'input'},
    {title: 'Склад', field: 'warehouse', width: 150, headerFilter: 'input'},
    {title: 'Ячейка', field: 'cell', width: 125, headerFilter: 'input'},
    {title: 'Категория', field: 'category', width: 140, headerFilter: 'input'},
    {title: 'Марка', field: 'brand', width: 120, headerFilter: 'input'},
    {title: 'Модель', field: 'car_model', width: 135, headerFilter: 'input'},
    {title: 'Поколение', field: 'generation', width: 105, headerFilter: 'input'},
    {title: 'Год', field: 'year', width: 90, hozAlign: 'right', sorter: 'number', headerFilter: 'input'},
    {title: 'ДВС', field: 'engine', width: 105, headerFilter: 'input'},
    {title: 'OEM', field: 'oem', width: 130, headerFilter: 'input'},
    {title: 'Состояние', field: 'condition', width: 130, headerFilter: 'input'},
    {title: 'Статус', field: 'status_label', width: 150, headerFilter: 'input'},
    {title: 'Мин. цена', field: 'min_price', width: 100, hozAlign: 'right', sorter: 'number',
     formatter: 'money', formatterParams: money},
    {title: 'Цена', field: 'price', width: 100, hozAlign: 'right', sorter: 'number',
     formatter: 'money', formatterParams: money, bottomCalc: 'sum', bottomCalcFormatter: 'money',
     bottomCalcFormatterParams: money},
    {title: 'Создано', field: 'created', width: 95},
  ];
  const groupable = columns.filter(c => !['id', 'barcode', 'price', 'min_price'].includes(c.field));

  const table = new Tabulator('#grid', {
    height: '100%',
    layout: 'fitData',
    index: 'id',
    columns: columns.map(c => ({...c, headerMenu: columnMenu})),
    columnDefaults: {headerFilterPlaceholder: 'фильтр…', tooltip: true},
    selectableRows: true,
    placeholder: 'Ничего не найдено',
    groupStartOpen: true,
    groupHeader: (value, count, data, group) => {
      const sum = data.reduce((s, r) => s + (r.price || 0), 0);
      return `${value || '(пусто)'} <span class="g-count">${count} шт.</span>` +
        (sum ? ` <span class="g-sum">${sum.toLocaleString('ru-RU')} ₽</span>` : '');
    },
    rowFormatter: row => {
      const d = row.getData();
      const el = row.getElement();
      el.classList.toggle('row-reserved', d.status === 'reserved');
      el.classList.toggle('row-transit', d.warehouse_kind === 'transit');
      el.classList.toggle('row-inactive', d.status === 'sold' || d.status === 'written_off');
    },
    locale: 'ru',
    langs: {ru: {data: {loading: 'Загрузка…', error: 'Ошибка'}, groups: {item: 'шт.', items: 'шт.'}}},
  });

  // Меню в заголовке колонки: группировать / скрыть / показать скрытые
  function columnMenu(e, column) {
    const items = [];
    const field = column.getField();
    if (groupable.some(c => c.field === field)) {
      items.push({label: 'Группировать по этой колонке', action: () => addGroup(field)});
    }
    items.push({label: 'Скрыть колонку', action: () => column.hide()});
    const hidden = table.getColumns().filter(c => !c.isVisible());
    if (hidden.length) {
      items.push({separator: true});
      hidden.forEach(c => items.push({label: 'Показать: ' + c.getDefinition().title, action: () => c.show()}));
    }
    return items;
  }

  // Двойной клик по строке — карточка детали
  table.on('rowDblClick', (e, row) => {
    window.open(STOCK.partUrl.replace('/0/', '/' + row.getData().id + '/'), '_blank');
  });

  // ---------- Группировка ----------
  groupable.forEach(c => {
    const o = document.createElement('option');
    o.value = c.field;
    o.textContent = c.title;
    groupAdd.appendChild(o);
  });
  groupAdd.addEventListener('change', () => {
    if (groupAdd.value) addGroup(groupAdd.value);
    groupAdd.value = '';
  });

  function titleOf(field) {
    return (columns.find(c => c.field === field) || {}).title || field;
  }

  function addGroup(field) {
    if (!groupFields.includes(field)) groupFields.push(field);
    applyGroups();
  }

  function applyGroups() {
    table.setGroupBy(groupFields.length ? groupFields.slice() : false);
    groupChips.innerHTML = '';
    groupFields.forEach((f, i) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = (i ? '› ' : '') + titleOf(f);
      const x = document.createElement('button');
      x.type = 'button';
      x.textContent = '×';
      x.title = 'Убрать группировку';
      x.onclick = () => { groupFields = groupFields.filter(g => g !== f); applyGroups(); };
      chip.appendChild(x);
      groupChips.appendChild(chip);
    });
    groupPanel.classList.toggle('has-groups', groupFields.length > 0);
  }

  // Перетаскивание заголовка колонки на панель группировки
  table.on('tableBuilt', () => {
    table.getColumns().forEach(col => {
      const field = col.getField();
      if (!groupable.some(c => c.field === field)) return;
      const title = col.getElement().querySelector('.tabulator-col-title');
      if (!title) return;
      title.setAttribute('draggable', 'true');
      title.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', field);
        e.dataTransfer.effectAllowed = 'copy';
      });
    });
    load();
  });
  groupPanel.addEventListener('dragover', e => { e.preventDefault(); groupPanel.classList.add('drop'); });
  groupPanel.addEventListener('dragleave', () => groupPanel.classList.remove('drop'));
  groupPanel.addEventListener('drop', e => {
    e.preventDefault();
    groupPanel.classList.remove('drop');
    const field = e.dataTransfer.getData('text/plain');
    if (groupable.some(c => c.field === field)) addGroup(field);
  });

  // ---------- Загрузка данных ----------
  let requestNo = 0;
  async function load() {
    const params = new URLSearchParams(new FormData(form));
    const my = ++requestNo;
    table.alert('Загрузка…');
    try {
      const resp = await fetch(STOCK.apiUrl + '?' + params, {headers: {Accept: 'application/json'}});
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      if (my !== requestNo) return;  // пришёл ответ на устаревший запрос
      await table.setData(data.rows);
      document.getElementById('total').textContent = data.total.toLocaleString('ru-RU');
      document.getElementById('shown-note').textContent =
        data.shown < data.total ? `показаны первые ${data.shown.toLocaleString('ru-RU')} — уточните фильтр` : '';
    } catch (err) {
      document.getElementById('total').textContent = 'ошибка загрузки';
    } finally {
      if (my === requestNo) table.clearAlert();
    }
  }

  let timer;
  form.addEventListener('change', () => { clearTimeout(timer); timer = setTimeout(load, 150); });
  form.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); load(); } });
  document.getElementById('btn-search').addEventListener('click', load);
  document.getElementById('btn-clear').addEventListener('click', () => {
    form.reset();
    brandModel.refresh('');
    table.clearHeaderFilter();
    load();
    document.getElementById('f-q').focus();
  });
  document.getElementById('btn-csv').addEventListener('click', () => {
    table.download('csv', 'ostatki.csv', {delimiter: ';', bom: true});
  });
})();
