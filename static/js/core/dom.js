/* =================================================================
   DOM — element query and manipulation helpers
   Exposes: window.DOM
   ================================================================= */

window.DOM = (() => {

  const $ = (selector, ctx = document) => ctx.querySelector(selector);
  const $$ = (selector, ctx = document) => [...ctx.querySelectorAll(selector)];

  function on(el, event, fn, opts) {
    if (!el) return;
    el.addEventListener(event, fn, opts);
  }

  function off(el, event, fn) {
    if (!el) return;
    el.removeEventListener(event, fn);
  }

  function once(el, event, fn) {
    if (!el) return;
    el.addEventListener(event, fn, { once: true });
  }

  function show(el) {
    if (el) el.style.display = '';
  }

  function hide(el) {
    if (el) el.style.display = 'none';
  }

  function toggle(el, force) {
    if (!el) return;
    const vis = force !== undefined ? force : el.style.display === 'none';
    el.style.display = vis ? '' : 'none';
  }

  function addClass(el, ...classes) {
    if (el) el.classList.add(...classes);
  }

  function removeClass(el, ...classes) {
    if (el) el.classList.remove(...classes);
  }

  function toggleClass(el, cls, force) {
    if (el) el.classList.toggle(cls, force);
  }

  function hasClass(el, cls) {
    return el ? el.classList.contains(cls) : false;
  }

  function setHTML(el, html) {
    if (el) el.innerHTML = html;
  }

  function setText(el, text) {
    if (el) el.textContent = text;
  }

  function attr(el, name, value) {
    if (!el) return undefined;
    if (value === undefined) return el.getAttribute(name);
    el.setAttribute(name, value);
  }

  function removeAttr(el, name) {
    if (el) el.removeAttribute(name);
  }

  function val(el) {
    if (!el) return '';
    return el.value;
  }

  function setVal(el, v) {
    if (el) el.value = v;
  }

  function createElement(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'class') el.className = v;
      else if (k === 'style') el.style.cssText = v;
      else if (k.startsWith('data-')) el.setAttribute(k, v);
      else el[k] = v;
    });
    children.forEach(child => {
      if (typeof child === 'string') el.appendChild(document.createTextNode(child));
      else if (child) el.appendChild(child);
    });
    return el;
  }

  function empty(el) {
    if (el) el.innerHTML = '';
  }

  function closestData(el, attr) {
    if (!el) return null;
    const closest = el.closest(`[data-${attr}]`);
    return closest ? closest.dataset[attr] : null;
  }

  return {
    $, $$, on, off, once, show, hide, toggle,
    addClass, removeClass, toggleClass, hasClass,
    setHTML, setText, attr, removeAttr, val, setVal,
    createElement, empty, closestData,
  };
})();
