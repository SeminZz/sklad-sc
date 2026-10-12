// Связка «Марка → Модель»: список моделей доступен только после выбора марки
// и содержит только модели этой марки. Используется на странице «Склад» и в карточке детали.
(function () {
  'use strict';

  function label(m) {
    let text = m.name;
    if (m.name_ru && m.name_ru.toLowerCase() !== m.name.toLowerCase()) text += ' (' + m.name_ru + ')';
    return text;
  }

  // brandSel, modelSel — элементы <select>; url — адрес /sklad/api/models/
  // opts.allLabel — подпись пустого варианта, когда марка выбрана («Все модели» или «---------»)
  window.linkBrandModel = function (brandSel, modelSel, url, opts) {
    opts = opts || {};
    const allLabel = opts.allLabel || 'Все модели';
    const noBrandLabel = opts.noBrandLabel || 'Сначала выберите марку';
    let requestNo = 0;

    function setOptions(list, keep) {
      modelSel.innerHTML = '';
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = brandSel.value ? allLabel : noBrandLabel;
      modelSel.appendChild(empty);
      list.forEach(m => {
        const o = document.createElement('option');
        o.value = m.id;
        o.textContent = label(m);
        if (m.years) o.title = 'Выпуск ' + m.years;
        modelSel.appendChild(o);
      });
      modelSel.disabled = !brandSel.value;
      if (keep && [...modelSel.options].some(o => o.value === keep)) modelSel.value = keep;
    }

    async function refresh(keep) {
      const brand = brandSel.value;
      if (!brand) { setOptions([], ''); return; }
      const my = ++requestNo;
      if (!keep) setOptions([], '');  // сразу сбросить старую модель, пока грузится список
      modelSel.disabled = true;
      try {
        const resp = await fetch(url + '?brand=' + encodeURIComponent(brand), {headers: {Accept: 'application/json'}});
        const data = await resp.json();
        if (my !== requestNo) return;  // пока грузили, марку уже сменили
        setOptions(data.models, keep);
      } catch (e) {
        modelSel.disabled = false;
      }
    }

    brandSel.addEventListener('change', () => refresh(''));
    return {refresh: refresh};
  };
})();
