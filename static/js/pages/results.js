/* =================================================================
   RESULTS PAGE - ENHANCED VERSION
   Exposes: window.ResultsPage
   ================================================================= */

window.ResultsPage = (() => {
  let _runs = [];
  let _filteredRuns = [];
  let _currentPage = 1;
  let _itemsPerPage = 20;
  let _sortColumn = 'date';
  let _sortDirection = 'desc';
  let _searchQuery = '';
  let _activeFilter = 'all';
  let _loading = false;

  // Mock data for demonstration - replace with actual API calls
  const MOCK_RUNS = [
    {
      id: 'run_001',
      strategy: 'EMA_Cross_v2',
      date: '2024-01-15',
      totalReturn: 15.4,
      trades: 127,
      winRate: 68.5,
      maxDrawdown: -8.2,
      sharpeRatio: 1.34,
      status: 'completed'
    },
    {
      id: 'run_002', 
      strategy: 'RSI_Divergence',
      date: '2024-01-14',
      totalReturn: -3.2,
      trades: 89,
      winRate: 42.7,
      maxDrawdown: -12.1,
      sharpeRatio: 0.67,
      status: 'completed'
    },
    {
      id: 'run_003',
      strategy: 'Bollinger_Squeeze',
      date: '2024-01-13',
      totalReturn: 22.8,
      trades: 156,
      winRate: 71.2,
      maxDrawdown: -5.4,
      sharpeRatio: 1.89,
      status: 'completed'
    },
    {
      id: 'run_004',
      strategy: 'MACD_Signal',
      date: '2024-01-12',
      totalReturn: 8.7,
      trades: 203,
      winRate: 55.2,
      maxDrawdown: -9.8,
      sharpeRatio: 1.12,
      status: 'running'
    },
    {
      id: 'run_005',
      strategy: 'Triple_EMA',
      date: '2024-01-11',
      totalReturn: -7.3,
      trades: 78,
      winRate: 38.5,
      maxDrawdown: -15.6,
      sharpeRatio: 0.23,
      status: 'failed'
    }
  ];

  function init() {
    const resultsPage = document.querySelector('[data-view="results"]');
    if (!resultsPage) return;

    loadData();
    bindEvents();
    updateStats();
  }

  function loadData() {
    _loading = true;
    showLoading();

    // Simulate API call
    setTimeout(() => {
      _runs = [...MOCK_RUNS];
      _filteredRuns = [..._runs];
      _loading = false;
      hideLoading();
      applyFilters();
      renderTable();
      updateStats();
      updatePagination();
    }, 1000);
  }

  function bindEvents() {
    // Search functionality
    const searchInput = document.getElementById('results-search');
    if (searchInput) {
      searchInput.addEventListener('input', debounce(handleSearch, 300));
    }

    // Filter chips
    document.querySelectorAll('.results-filter-chip').forEach(chip => {
      chip.addEventListener('click', handleFilterClick);
    });

    // Table header sorting
    document.querySelectorAll('[data-sort]').forEach(header => {
      header.addEventListener('click', handleSort);
    });

    // Pagination
    document.getElementById('prev-page')?.addEventListener('click', () => changePage(_currentPage - 1));
    document.getElementById('next-page')?.addEventListener('click', () => changePage(_currentPage + 1));
  }

  function handleSearch(event) {
    _searchQuery = event.target.value.toLowerCase();
    _currentPage = 1;
    applyFilters();
    renderTable();
    updatePagination();
  }

  function handleFilterClick(event) {
    // Remove active class from all chips
    document.querySelectorAll('.results-filter-chip').forEach(chip => {
      chip.classList.remove('active');
    });
    
    // Add active class to clicked chip
    event.target.classList.add('active');
    _activeFilter = event.target.dataset.filter;
    _currentPage = 1;
    applyFilters();
    renderTable();
    updatePagination();
  }

  function handleSort(event) {
    const column = event.target.dataset.sort;
    if (_sortColumn === column) {
      _sortDirection = _sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      _sortColumn = column;
      _sortDirection = 'desc';
    }
    
    applyFilters();
    renderTable();
    updateSortIndicators();
  }

  function applyFilters() {
    let filtered = [..._runs];

    // Apply search filter
    if (_searchQuery) {
      filtered = filtered.filter(run => 
        run.strategy.toLowerCase().includes(_searchQuery) ||
        run.id.toLowerCase().includes(_searchQuery)
      );
    }

    // Apply status filter
    switch (_activeFilter) {
      case 'profitable':
        filtered = filtered.filter(run => run.totalReturn > 0);
        break;
      case 'recent':
        const oneWeekAgo = new Date();
        oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
        filtered = filtered.filter(run => new Date(run.date) >= oneWeekAgo);
        break;
      case 'high-volume':
        filtered = filtered.filter(run => run.trades > 150);
        break;
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aVal = a[_sortColumn];
      let bVal = b[_sortColumn];

      if (_sortColumn === 'date') {
        aVal = new Date(aVal);
        bVal = new Date(bVal);
      }

      if (_sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });

    _filteredRuns = filtered;
  }

  function renderTable() {
    const tableBody = document.getElementById('results-table-body');
    if (!tableBody) return;

    if (_filteredRuns.length === 0) {
      showEmptyState();
      return;
    }

    hideEmptyState();

    const startIndex = (_currentPage - 1) * _itemsPerPage;
    const endIndex = startIndex + _itemsPerPage;
    const pageRuns = _filteredRuns.slice(startIndex, endIndex);

    tableBody.innerHTML = pageRuns.map(run => `
      <tr class="results-table-row" data-run-id="${run.id}">
        <td class="results-cell-strategy">${run.strategy}</td>
        <td class="results-cell-date">${formatDate(run.date)}</td>
        <td class="results-cell-profit ${getProfitClass(run.totalReturn)}">
          ${formatPercent(run.totalReturn)}
        </td>
        <td>${run.trades}</td>
        <td>${formatPercent(run.winRate)}</td>
        <td class="results-cell-profit negative">${formatPercent(run.maxDrawdown)}</td>
        <td>${run.sharpeRatio.toFixed(2)}</td>
        <td>
          <span class="results-cell-status ${run.status}">${capitalizeFirst(run.status)}</span>
        </td>
        <td class="results-cell-actions">
          <button class="results-action-btn" onclick="viewDetails('${run.id}')">View</button>
          <button class="results-action-btn primary" onclick="openExplorer('${run.id}')">Explore</button>
        </td>
      </tr>
    `).join('');

    // Add click handlers for rows
    tableBody.querySelectorAll('.results-table-row').forEach(row => {
      row.addEventListener('click', () => {
        const runId = row.dataset.runId;
        openExplorer(runId);
      });
    });
  }

  function updateStats() {
    const totalRuns = _runs.length;
    const profitableRuns = _runs.filter(run => run.totalReturn > 0);
    const avgReturn = _runs.reduce((sum, run) => sum + run.totalReturn, 0) / totalRuns;
    const bestStrategy = _runs.reduce((best, run) => 
      run.totalReturn > (best?.totalReturn || -Infinity) ? run : best, null);

    document.getElementById('total-runs').textContent = totalRuns;
    document.getElementById('avg-return').textContent = formatPercent(avgReturn);
    document.getElementById('best-strategy').textContent = bestStrategy?.strategy || '-';
    document.getElementById('success-rate').textContent = formatPercent((profitableRuns.length / totalRuns) * 100);

    // Update change indicators
    document.getElementById('runs-change').textContent = `+${Math.floor(totalRuns * 0.2)} this week`;
    document.getElementById('return-change').textContent = `${avgReturn > 0 ? '+' : ''}${(avgReturn * 0.1).toFixed(1)}% vs last month`;
    document.getElementById('best-return').textContent = `${formatPercent(bestStrategy?.totalReturn || 0)} return`;
    document.getElementById('success-change').textContent = `${profitableRuns.length} profitable`;

    // Update change classes
    updateChangeClass('return-change', avgReturn);
    updateChangeClass('success-change', profitableRuns.length / totalRuns);
  }

  function updateChangeClass(elementId, value) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.classList.remove('positive', 'negative');
    if (value > 0) {
      element.classList.add('positive');
    } else if (value < 0) {
      element.classList.add('negative');
    }
  }

  function updatePagination() {
    const totalPages = Math.ceil(_filteredRuns.length / _itemsPerPage);
    const startItem = (_currentPage - 1) * _itemsPerPage + 1;
    const endItem = Math.min(_currentPage * _itemsPerPage, _filteredRuns.length);

    document.getElementById('pagination-start').textContent = startItem;
    document.getElementById('pagination-end').textContent = endItem;
    document.getElementById('pagination-total').textContent = _filteredRuns.length;

    // Update pagination buttons
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    
    if (prevBtn) {
      prevBtn.disabled = _currentPage <= 1;
    }
    if (nextBtn) {
      nextBtn.disabled = _currentPage >= totalPages;
    }

    // Update page numbers
    const numbersContainer = document.getElementById('pagination-numbers');
    if (numbersContainer) {
      numbersContainer.innerHTML = generatePageNumbers(totalPages);
    }
  }

  function generatePageNumbers(totalPages) {
    const numbers = [];
    const maxVisible = 5;
    let startPage = Math.max(1, _currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage + 1 < maxVisible) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      const isActive = i === _currentPage;
      numbers.push(`
        <button class="results-pagination-btn ${isActive ? 'active' : ''}" 
                onclick="window.ResultsPage.changePage(${i})">
          ${i}
        </button>
      `);
    }

    return numbers.join('');
  }

  function changePage(page) {
    const totalPages = Math.ceil(_filteredRuns.length / _itemsPerPage);
    if (page < 1 || page > totalPages) return;
    
    _currentPage = page;
    renderTable();
    updatePagination();
  }

  function updateSortIndicators() {
    // Remove all sort indicators
    document.querySelectorAll('[data-sort]').forEach(header => {
      header.classList.remove('sorted-asc', 'sorted-desc');
    });

    // Add indicator to current sort column
    const currentHeader = document.querySelector(`[data-sort="${_sortColumn}"]`);
    if (currentHeader) {
      currentHeader.classList.add(`sorted-${_sortDirection}`);
    }
  }

  function showLoading() {
    const loading = document.getElementById('results-loading');
    const container = document.querySelector('.results-table-container');
    if (loading && container) {
      loading.style.display = 'flex';
      container.style.display = 'none';
    }
  }

  function hideLoading() {
    const loading = document.getElementById('results-loading');
    const container = document.querySelector('.results-table-container');
    if (loading && container) {
      loading.style.display = 'none';
      container.style.display = 'block';
    }
  }

  function showEmptyState() {
    const empty = document.getElementById('results-empty');
    const container = document.querySelector('.results-table-container');
    if (empty && container) {
      empty.style.display = 'block';
      container.style.display = 'none';
    }
  }

  function hideEmptyState() {
    const empty = document.getElementById('results-empty');
    const container = document.querySelector('.results-table-container');
    if (empty && container) {
      empty.style.display = 'none';
      container.style.display = 'block';
    }
  }

  // Utility functions
  function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  }

  function formatPercent(value) {
    return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
  }

  function getProfitClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
  }

  function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Global functions for button clicks
  window.viewDetails = function(runId) {
    console.log('Viewing details for run:', runId);
    // Implement view details functionality
  };

  window.openExplorer = function(runId) {
    console.log('Opening explorer for run:', runId);
    // Implement result explorer functionality
    if (window.ResultExplorer && window.ResultExplorer.open) {
      window.ResultExplorer.open(runId);
    }
  };

  // Public API
  return {
    init,
    changePage,
    refresh: loadData
  };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', window.ResultsPage.init);
} else {
  window.ResultsPage.init();
}