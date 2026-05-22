// Info-popover binding for [data-info-trigger] elements.
// Renders via HTML popover="auto" (top-layer, escapes overflow:auto).
// Desktop: hover (with 150ms delay) + keyboard focus open the popover.
// Touch: 500ms long-press opens it and suppresses the following click
// so a link/button trigger doesn't navigate.
(function () {
  'use strict';

  const HOVER_DELAY_MS = 150;
  const LONGPRESS_MS = 500;
  const GAP_PX = 4;
  const EDGE_PX = 8;
  const SUPPRESS_RESET_MS = 100;
  const PRESS_MOVE_TOLERANCE_PX = 10;

  function dbg() {
    if (!window.__popoverDebug) return;
    var args = Array.prototype.slice.call(arguments);
    args.unshift('[popover]');
    console.log.apply(console, args);
  }

  function positionPopover(trigger, panel) {
    panel.style.position = 'fixed';
    panel.style.margin = '0';
    const r = trigger.getBoundingClientRect();
    let top = r.bottom + GAP_PX;
    let left = r.left;
    const h = panel.offsetHeight;
    const w = panel.offsetWidth;
    if (top + h > window.innerHeight - EDGE_PX) {
      top = r.top - h - GAP_PX;
    }
    if (top < EDGE_PX) {
      top = r.bottom + GAP_PX;
    }
    if (left + w > window.innerWidth - EDGE_PX) {
      left = window.innerWidth - w - EDGE_PX;
    }
    if (left < EDGE_PX) {
      left = EDGE_PX;
    }
    panel.style.top = top + 'px';
    panel.style.left = left + 'px';
  }

  function showPopover(trigger, panel) {
    dbg('showPopover called for', panel.id, 'popover-supported?', typeof panel.showPopover === 'function');
    try {
      if (!panel.matches(':popover-open')) {
        panel.showPopover();
        dbg('showPopover() OK, now open?', panel.matches(':popover-open'));
      }
    } catch (e) {
      console.warn('popover.js: showPopover failed', e, panel);
      dbg('showPopover THREW:', e.message);
      return;
    }
    positionPopover(trigger, panel);
    dbg('positioned at', panel.style.top, panel.style.left, 'size', panel.offsetWidth, 'x', panel.offsetHeight);
  }

  function hidePopover(panel) {
    try {
      if (panel.matches(':popover-open')) {
        panel.hidePopover();
      }
    } catch (e) {
      console.warn('popover.js: hidePopover failed', e, panel);
    }
  }

  function bindTrigger(trigger) {
    const panelId = trigger.dataset.infoTrigger;
    const panel = document.getElementById(panelId);
    if (!panel) return;

    const hoverSupported = window.matchMedia('(hover: hover)').matches;
    let hoverTimer = null;
    let pressTimer = null;
    let suppressClick = false;

    // Desktop hover (with small delay against flicker)
    trigger.addEventListener('mouseenter', function () {
      if (!hoverSupported) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function () {
        showPopover(trigger, panel);
      }, HOVER_DELAY_MS);
    });
    trigger.addEventListener('mouseleave', function () {
      clearTimeout(hoverTimer);
      hidePopover(panel);
    });

    // Keyboard focus
    trigger.addEventListener('focus', function () {
      showPopover(trigger, panel);
    });
    trigger.addEventListener('blur', function () {
      hidePopover(panel);
    });

    // Touch long-press
    //
    // We DELIBERATELY do not cancel on `pointercancel` or `pointerleave`.
    // Mobile browsers fire `pointercancel` when they decide to "take over"
    // the gesture for their own long-press handling (link callout, context
    // menu) — which happens at roughly the same 500 ms threshold we use.
    // Cancelling on it would race against the browser and lose. Instead we
    // suppress the browser's own UI with -webkit-touch-callout:none + the
    // contextmenu listener below, and let our timer run to completion.
    //
    // The pointermove > tolerance check below already catches scroll/drag
    // intent, so pointerleave is not needed as a separate cancel signal.
    let pressOriginX = 0;
    let pressOriginY = 0;
    let pressActive = false;
    trigger.addEventListener('pointerdown', function (e) {
      dbg('pointerdown', e.pointerType, 'panel=', panelId);
      if (e.pointerType !== 'touch') return;
      pressOriginX = e.clientX;
      pressOriginY = e.clientY;
      pressActive = true;
      clearTimeout(pressTimer);
      pressTimer = setTimeout(function () {
        dbg('long-press timer FIRED for', panelId);
        showPopover(trigger, panel);
        suppressClick = true;
        setTimeout(function () { suppressClick = false; }, SUPPRESS_RESET_MS);
      }, LONGPRESS_MS);
    });
    const cancelPress = function (reason) {
      if (pressActive) dbg('press CANCELLED', reason || '');
      clearTimeout(pressTimer);
      pressActive = false;
    };
    trigger.addEventListener('pointerup', function () { cancelPress('pointerup'); });
    trigger.addEventListener('pointermove', function (e) {
      const dx = Math.abs(e.clientX - pressOriginX);
      const dy = Math.abs(e.clientY - pressOriginY);
      if (dx > PRESS_MOVE_TOLERANCE_PX || dy > PRESS_MOVE_TOLERANCE_PX) {
        cancelPress('pointermove>' + PRESS_MOVE_TOLERANCE_PX + 'px (dx=' + dx + ' dy=' + dy + ')');
      }
    });
    trigger.addEventListener('pointercancel', function () { dbg('pointercancel fired (NOT cancelling timer)'); });
    trigger.addEventListener('pointerleave', function () { dbg('pointerleave fired (NOT cancelling timer)'); });

    // Suppress the browser's long-press context menu (Android Chrome) and
    // any right-click menu on desktop for trigger elements.
    trigger.addEventListener('contextmenu', function (e) {
      dbg('contextmenu prevented');
      e.preventDefault();
    });

    // Click suppression after long-press (capture phase to beat link/button default)
    trigger.addEventListener('click', function (e) {
      if (suppressClick) {
        e.preventDefault();
        e.stopPropagation();
        suppressClick = false;
      }
    }, true);

    // Reposition on resize/scroll while popover is open. We attach the
    // window listeners only when the popover opens, and remove them when
    // it closes, so listener count stays bounded regardless of trigger
    // count on the page.
    const reposition = function () {
      positionPopover(trigger, panel);
    };
    panel.addEventListener('toggle', function (e) {
      if (e.newState === 'open') {
        window.addEventListener('resize', reposition);
        window.addEventListener('scroll', reposition, true);
      } else {
        window.removeEventListener('resize', reposition);
        window.removeEventListener('scroll', reposition, true);
      }
    });
  }

  function initInfoPopovers() {
    var triggers = document.querySelectorAll('[data-info-trigger]');
    dbg('init: binding', triggers.length, 'triggers; popover supported?',
        typeof HTMLElement.prototype.showPopover === 'function',
        'hover:hover?', window.matchMedia('(hover: hover)').matches);
    triggers.forEach(bindTrigger);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInfoPopovers);
  } else {
    initInfoPopovers();
  }
})();
