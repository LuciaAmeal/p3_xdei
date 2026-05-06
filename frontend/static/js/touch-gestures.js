(function (global) {
  function getHammer() {
    if (typeof global.Hammer === 'undefined') {
      return null;
    }

    return global.Hammer;
  }

  function shiftTimeline(delta) {
    const slider = document.getElementById('timeline-slider');
    if (!slider || slider.disabled) {
      return;
    }

    const min = Number(slider.min || 0);
    const max = Number(slider.max || 0);
    const current = Number(slider.value || 0);
    const next = Math.min(max, Math.max(min, current + delta));

    if (next === current) {
      return;
    }

    slider.value = String(next);
    slider.dispatchEvent(new Event('input', { bubbles: true }));
    slider.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function dispatchResetView() {
    global.dispatchEvent(new CustomEvent('xdei:scene3d-reset-view'));
  }

  function bindTimelineGestures(Hammer) {
    const timeline = document.getElementById('timeline-panel');
    if (!timeline) {
      return;
    }

    const manager = new Hammer.Manager(timeline);
    manager.add(new Hammer.Swipe({ direction: Hammer.DIRECTION_HORIZONTAL, threshold: 16, velocity: 0.18 }));

    manager.on('swipeleft', function () {
      shiftTimeline(1);
    });

    manager.on('swiperight', function () {
      shiftTimeline(-1);
    });
  }

  function bindViewportGestures(Hammer) {
    const sceneRoot = document.getElementById('scene-root');
    if (!sceneRoot) {
      return;
    }

    const manager = new Hammer.Manager(sceneRoot);
    manager.add(new Hammer.Tap({ event: 'doubletap', taps: 2 }));
    manager.add(new Hammer.Tap({ event: 'singletap', taps: 1 }));
    manager.add(new Hammer.Press({ event: 'longpress', time: 500 }));
    manager.get('singletap').recognizeWith('doubletap');
    manager.get('doubletap').requireFailure('singletap');

    manager.on('doubletap', function () {
      dispatchResetView();
    });

    manager.on('longpress', function () {
      global.dispatchEvent(new CustomEvent('xdei:detail-longpress'));
    });

    manager.on('singletap', function (event) {
      // Preserve tap interaction by forwarding a synthetic click.
      const src = event && event.srcEvent;
      if (!src || typeof src.clientX !== 'number' || typeof src.clientY !== 'number') {
        return;
      }

      const clickEvent = new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        clientX: src.clientX,
        clientY: src.clientY,
      });

      src.target.dispatchEvent(clickEvent);
    });
  }

  function initFallbackGestures() {
    const sceneRoot = document.getElementById('scene-root');
    if (!sceneRoot) {
      return;
    }

    let lastTapTs = 0;
    sceneRoot.addEventListener('touchend', function () {
      const now = Date.now();
      if (now - lastTapTs < 280) {
        dispatchResetView();
      }
      lastTapTs = now;
    }, { passive: true });
  }

  function init() {
    const Hammer = getHammer();
    if (!Hammer) {
      initFallbackGestures();
      return;
    }

    bindViewportGestures(Hammer);
    bindTimelineGestures(Hammer);
  }

  if (document.readyState === 'loading') {
    global.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})(window);
