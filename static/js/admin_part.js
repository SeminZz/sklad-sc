// Карточка детали в админке: список «Модель» зависит от выбранной «Марки».
document.addEventListener('DOMContentLoaded', function () {
  'use strict';
  const brand = document.getElementById('id_brand');
  const model = document.getElementById('id_car_model');
  if (!brand || !model || !window.linkBrandModel) return;
  window.linkBrandModel(brand, model, model.dataset.modelsUrl, {allLabel: '---------'});
  if (!brand.value) model.disabled = true;
  // Перед отправкой формы список должен быть включён, иначе браузер не отправит значение
  model.form && model.form.addEventListener('submit', () => { model.disabled = false; });
});
