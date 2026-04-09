/* =================================================================
   CHARTS - Animated SVG Chart Components for Results
   Exposes: window.Charts
   ================================================================= */

window.Charts = (() => {
  'use strict';

  /**
   * Create an animated line chart
   * @param {HTMLElement} container - Container element
   * @param {Array} data - Array of {label, value} objects
   * @param {Object} options - Chart options
   */
  function createLineChart(container, data, options = {}) {
    if (!container || !data || data.length === 0) return null;

    const {
      color = 'var(--accent)',
      area = true,
      height = 200,
      animate = true,
      showPoints = false
    } = options;

    const width = container.clientWidth || 400;
    const padding = { top: 10, right: 10, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Calculate scales
    const values = data.map(d => d.value);
    const minValue = Math.min(...values, 0);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    const getX = (index) => padding.left + (index / (data.length - 1 || 1)) * chartWidth;
    const getY = (value) => padding.top + chartHeight - ((value - minValue) / valueRange) * chartHeight;

    // Create SVG
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.classList.add('chart-canvas');

    // Create defs for gradients
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    if (area) {
      const gradientId = `gradient-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
      gradient.setAttribute('id', gradientId);
      gradient.setAttribute('x1', '0%');
      gradient.setAttribute('y1', '0%');
      gradient.setAttribute('x2', '0%');
      gradient.setAttribute('y2', '100%');

      const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
      stop1.setAttribute('offset', '0%');
      stop1.setAttribute('stop-color', color);
      stop1.setAttribute('stop-opacity', '0.3');

      const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
      stop2.setAttribute('offset', '100%');
      stop2.setAttribute('stop-color', color);
      stop2.setAttribute('stop-opacity', '0');

      gradient.appendChild(stop1);
      gradient.appendChild(stop2);
      defs.appendChild(gradient);

      // Create area path
      const areaPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      let areaD = `M ${getX(0)} ${getY(minValue)}`;
      data.forEach((d, i) => {
        areaD += ` L ${getX(i)} ${getY(d.value)}`;
      });
      areaD += ` L ${getX(data.length - 1)} ${getY(minValue)} Z`;
      areaPath.setAttribute('d', areaD);
      areaPath.setAttribute('fill', `url(#${gradientId})`);
      areaPath.style.opacity = '0';
      if (animate) {
        areaPath.style.animation = 'chartFadeIn 0.8s ease-out 0.5s forwards';
      } else {
        areaPath.style.opacity = '1';
      }
      svg.appendChild(areaPath);
    }
    svg.appendChild(defs);

    // Create grid lines
    const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gridGroup.setAttribute('class', 'chart-grid');
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight * i) / 4;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', padding.left);
      line.setAttribute('y1', y);
      line.setAttribute('x2', width - padding.right);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', 'var(--border-subtle)');
      line.setAttribute('stroke-width', '1');
      line.setAttribute('stroke-dasharray', '2,2');
      gridGroup.appendChild(line);
    }
    svg.appendChild(gridGroup);

    // Create line path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    let d = `M ${getX(0)} ${getY(data[0].value)}`;
    for (let i = 1; i < data.length; i++) {
      d += ` L ${getX(i)} ${getY(data[i].value)}`;
    }
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '2');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');

    if (animate) {
      const length = 1000;
      path.style.strokeDasharray = length;
      path.style.strokeDashoffset = length;
      path.classList.add('chart-line-path');
    }
    svg.appendChild(path);

    // Add points if enabled
    if (showPoints) {
      data.forEach((d, i) => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', getX(i));
        circle.setAttribute('cy', getY(d.value));
        circle.setAttribute('r', '4');
        circle.setAttribute('fill', 'var(--surface-1)');
        circle.setAttribute('stroke', color);
        circle.setAttribute('stroke-width', '2');
        circle.style.opacity = '0';
        circle.style.animation = `chartFadeIn 0.3s ease-out ${0.5 + i * 0.05}s forwards`;
        svg.appendChild(circle);
      });
    }

    // Create axes
    const axisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    axisGroup.setAttribute('class', 'chart-axes');

    // Y-axis labels
    for (let i = 0; i <= 4; i++) {
      const value = maxValue - (valueRange * i) / 4;
      const y = padding.top + (chartHeight * i) / 4;
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', padding.left - 8);
      text.setAttribute('y', y + 4);
      text.setAttribute('text-anchor', 'end');
      text.setAttribute('fill', 'var(--text-muted)');
      text.setAttribute('font-size', '10');
      text.setAttribute('font-family', 'var(--font-mono)');
      text.textContent = formatValue(value);
      axisGroup.appendChild(text);
    }

    // X-axis labels (show first, middle, last)
    const xLabels = [0, Math.floor(data.length / 2), data.length - 1];
    xLabels.forEach(i => {
      if (i < data.length) {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', getX(i));
        text.setAttribute('y', height - 8);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', 'var(--text-muted)');
        text.setAttribute('font-size', '10');
        text.textContent = data[i].label;
        axisGroup.appendChild(text);
      }
    });

    svg.appendChild(axisGroup);
    container.appendChild(svg);

    // Add tooltip
    const tooltip = createTooltip(container);

    // Add hover interaction
    svg.addEventListener('mousemove', (e) => {
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const index = Math.round(((x - padding.left) / chartWidth) * (data.length - 1));
      if (index >= 0 && index < data.length) {
        const point = data[index];
        tooltip.show(e.clientX, e.clientY, `${point.label}: ${formatValue(point.value)}`);
      }
    });

    svg.addEventListener('mouseleave', () => {
      tooltip.hide();
    });

    return svg;
  }

  /**
   * Create an animated bar chart
   * @param {HTMLElement} container - Container element
   * @param {Array} data - Array of {label, value} objects
   * @param {Object} options - Chart options
   */
  function createBarChart(container, data, options = {}) {
    if (!container || !data || data.length === 0) return null;

    const {
      positiveColor = 'var(--green)',
      negativeColor = 'var(--red)',
      height = 200,
      animate = true
    } = options;

    const width = container.clientWidth || 400;
    const padding = { top: 10, right: 10, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Calculate scales
    const values = data.map(d => d.value);
    const maxValue = Math.max(...values.map(Math.abs));
    const zeroY = padding.top + chartHeight / 2;

    const getBarHeight = (value) => (Math.abs(value) / maxValue) * (chartHeight / 2);
    const getBarY = (value) => value >= 0 ? zeroY - getBarHeight(value) : zeroY;

    // Create SVG
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.classList.add('chart-canvas');

    // Create grid lines
    const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gridGroup.setAttribute('class', 'chart-grid');
    [0, 0.5, 1].forEach(i => {
      const y = padding.top + chartHeight * i;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', padding.left);
      line.setAttribute('y1', y);
      line.setAttribute('x2', width - padding.right);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', 'var(--border-subtle)');
      line.setAttribute('stroke-width', '1');
      line.setAttribute('stroke-dasharray', i === 0.5 ? '' : '2,2');
      gridGroup.appendChild(line);
    });
    svg.appendChild(gridGroup);

    // Calculate bar width
    const barWidth = Math.max(4, (chartWidth / data.length) * 0.7);
    const barSpacing = chartWidth / data.length;

    // Create bars
    data.forEach((d, i) => {
      const barHeight = getBarHeight(d.value);
      const barX = padding.left + i * barSpacing + (barSpacing - barWidth) / 2;
      const barY = getBarY(d.value);
      const color = d.value >= 0 ? positiveColor : negativeColor;

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', barX);
      rect.setAttribute('y', barY);
      rect.setAttribute('width', barWidth);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('fill', color);
      rect.setAttribute('rx', '2');
      rect.classList.add('chart-bar');

      if (animate) {
        rect.style.animationDelay = `${i * 0.02}s`;
      }

      svg.appendChild(rect);
    });

    // Create axes
    const axisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    axisGroup.setAttribute('class', 'chart-axes');

    // Y-axis labels
    [-maxValue, 0, maxValue].forEach((value, i) => {
      const y = i === 0 ? padding.top + chartHeight : i === 1 ? zeroY : padding.top;
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', padding.left - 8);
      text.setAttribute('y', y + 4);
      text.setAttribute('text-anchor', 'end');
      text.setAttribute('fill', 'var(--text-muted)');
      text.setAttribute('font-size', '10');
      text.setAttribute('font-family', 'var(--font-mono)');
      text.textContent = formatValue(value);
      axisGroup.appendChild(text);
    });

    // X-axis labels (show first, middle, last)
    const xLabels = [0, Math.floor(data.length / 2), data.length - 1];
    xLabels.forEach(i => {
      if (i < data.length) {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', padding.left + i * barSpacing + barSpacing / 2);
        text.setAttribute('y', height - 8);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', 'var(--text-muted)');
        text.setAttribute('font-size', '10');
        text.textContent = data[i].label;
        axisGroup.appendChild(text);
      }
    });

    svg.appendChild(axisGroup);
    container.appendChild(svg);

    // Add tooltip
    const tooltip = createTooltip(container);

    // Add hover interaction
    svg.addEventListener('mousemove', (e) => {
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const index = Math.floor(((x - padding.left) / chartWidth) * data.length);
      if (index >= 0 && index < data.length) {
        const point = data[index];
        tooltip.show(e.clientX, e.clientY, `${point.label}: ${formatValue(point.value)}`);
      }
    });

    svg.addEventListener('mouseleave', () => {
      tooltip.hide();
    });

    return svg;
  }

  /**
   * Create a tooltip element
   */
  function createTooltip(container) {
    const tooltip = document.createElement('div');
    tooltip.className = 'chart-tooltip';
    container.style.position = 'relative';
    container.appendChild(tooltip);

    return {
      show(x, y, text) {
        tooltip.textContent = text;
        tooltip.classList.add('visible');

        // Position relative to container
        const rect = container.getBoundingClientRect();
        const relX = x - rect.left;
        const relY = y - rect.top;

        tooltip.style.left = `${relX}px`;
        tooltip.style.top = `${relY - 30}px`;
        tooltip.style.transform = 'translateX(-50%)';
      },
      hide() {
        tooltip.classList.remove('visible');
      }
    };
  }

  /**
   * Format a numeric value for display
   */
  function formatValue(value) {
    if (Math.abs(value) >= 1000000) {
      return (value / 1000000).toFixed(1) + 'M';
    } else if (Math.abs(value) >= 1000) {
      return (value / 1000).toFixed(1) + 'K';
    } else if (Math.abs(value) >= 1) {
      return value.toFixed(1);
    } else {
      return value.toFixed(3);
    }
  }

  /**
   * Create a chart card with header
   */
  function createChartCard(title, value, chartType, data, options = {}) {
    const container = document.createElement('div');
    container.className = 'chart-container';

    const header = document.createElement('div');
    header.className = 'chart-header';

    const titleEl = document.createElement('div');
    titleEl.className = 'chart-title';
    titleEl.textContent = title;

    const valueEl = document.createElement('div');
    valueEl.className = 'chart-value';
    valueEl.textContent = value;

    header.appendChild(titleEl);
    header.appendChild(valueEl);
    container.appendChild(header);

    const canvasWrapper = document.createElement('div');
    canvasWrapper.className = 'chart-canvas-wrapper';
    container.appendChild(canvasWrapper);

    // Create the appropriate chart
    if (chartType === 'line') {
      createLineChart(canvasWrapper, data, options);
    } else if (chartType === 'bar') {
      createBarChart(canvasWrapper, data, options);
    }

    return container;
  }

  /**
   * Update all charts in a container (responsive)
   */
  function updateCharts(container) {
    const charts = container.querySelectorAll('.chart-canvas');
    charts.forEach(chart => {
      const wrapper = chart.parentElement;
      const data = chart._data;
      const options = chart._options;
      const type = chart._type;

      if (data && options && type) {
        wrapper.innerHTML = '';
        if (type === 'line') {
          createLineChart(wrapper, data, options);
        } else if (type === 'bar') {
          createBarChart(wrapper, data, options);
        }
      }
    });
  }

  // Public API
  return {
    createLineChart,
    createBarChart,
    createChartCard,
    updateCharts,
    formatValue
  };
})();
