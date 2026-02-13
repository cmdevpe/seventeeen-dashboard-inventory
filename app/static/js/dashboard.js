// API Base URL - Siempre relativa para evitar problemas cross-origin
const API_URL = "/api";

// Chart instances
let suppliersChart = null;
let categoriesChart = null;
let brandsChart = null;

// Pagination state
let currentPage = 1;

// Format currency
const formatCurrency = (value) => {
  return new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: "PEN",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

// Format number
const formatNumber = (value) => {
  return new Intl.NumberFormat("es-PE").format(value);
};

// Upload Modal Helpers
function showUploadModal() {
  document.getElementById("upload-modal").classList.remove("hidden");
}
function hideUploadModal() {
  document.getElementById("upload-modal").classList.add("hidden");
}
function updateUploadProgress(percent, status, title = null) {
  document.getElementById("upload-progress").style.width = percent + "%";
  document.getElementById("upload-percent").textContent = percent + "%";
  document.getElementById("upload-status").textContent = status;
  if (title) document.getElementById("upload-title").textContent = title;
}

// Update status indicator
function updateStatus(isConnected, message) {
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  if (!dot || !text) return;

  if (isConnected) {
    dot.className = "w-2 h-2 rounded-full bg-green-500 animate-pulse";
    text.textContent = message || "Conectado";
    text.className = "text-xs text-green-500";
  } else {
    dot.className = "w-2 h-2 rounded-full bg-red-500";
    text.textContent = message || "Desconectado";
    text.className = "text-xs text-red-400";
  }
}

// Upload Excel file
async function uploadExcel(event) {
  const file = event.target.files[0];
  if (!file) return;

  showUploadModal();
  updateUploadProgress(0, "Preparando archivo...", "Subiendo archivo...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    // Stage 1: Uploading (0-30%)
    let progress = 0;
    const uploadInterval = setInterval(() => {
      if (progress < 30) {
        progress += 5;
        updateUploadProgress(progress, "Subiendo " + file.name);
      }
    }, 100);

    const response = await fetch(`${API_URL}/upload`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });

    clearInterval(uploadInterval);
    updateUploadProgress(30, "Archivo recibido");

    // Stage 2: Processing (30-70%)
    updateUploadProgress(40, "Procesando datos...", "Procesando Excel...");
    const data = await response.json();

    if (response.ok) {
      updateUploadProgress(70, data.message);

      // Stage 3: Loading dashboard (70-100%)
      updateUploadProgress(80, "Actualizando dashboard...", "Cargando datos...");
      const loadSuccess = await loadData();

      if (loadSuccess) {
        updateUploadProgress(100, "¡Completado!");
        setTimeout(() => {
          hideUploadModal();
          updateStatus(true, data.message);
        }, 500);
      } else {
        hideUploadModal();
        updateStatus(false, "Datos subidos pero error al procesar");
      }
    } else {
      hideUploadModal();
      updateStatus(false, data.error || "Error al cargar");
    }
  } catch (error) {
    console.error("Upload error:", error);
    hideUploadModal();
    updateStatus(false, "Error de conexión");
  }

  // Reset file input
  event.target.value = "";
}

// ==================== LOAD DATA ====================

async function loadData() {
  try {
    document.getElementById("empty-state").classList.add("hidden");
    document.getElementById("loading-state").classList.remove("hidden");
    document.getElementById("loading-state").innerHTML = `
      <div class="loader mb-4"></div>
      <p class="text-slate-500">Cargando análisis de inventario...</p>
    `;
    document.getElementById("dashboard-content").classList.add("hidden");

    const [
      kpisRes,
      stockStatusRes,
      suppliersRes,
      categoriesRes,
      brandsRes,
      topProductsRes,
      alertsRes,
      metadataRes,
    ] = await Promise.all([
      fetch(`${API_URL}/kpis`, { credentials: "include" }),
      fetch(`${API_URL}/stock-status`, { credentials: "include" }),
      fetch(`${API_URL}/suppliers`, { credentials: "include" }),
      fetch(`${API_URL}/categories`, { credentials: "include" }),
      fetch(`${API_URL}/brands`, { credentials: "include" }),
      fetch(`${API_URL}/top-products`, { credentials: "include" }),
      fetch(`${API_URL}/alerts`, { credentials: "include" }),
      fetch(`${API_URL}/metadata`, { credentials: "include" }),
    ]);

    // Verificar que TODAS las respuestas sean exitosas
    const allResponses = [kpisRes, stockStatusRes, suppliersRes, categoriesRes, brandsRes, topProductsRes, alertsRes, metadataRes];
    const failedRes = allResponses.find(r => !r.ok);
    if (failedRes) {
      const errData = await failedRes.json().catch(() => ({}));
      console.error("API error:", failedRes.url, failedRes.status, errData);
      throw new Error(errData.error || "API not available");
    }

    const kpis = await kpisRes.json();
    const stockStatus = await stockStatusRes.json();
    const suppliers = await suppliersRes.json();
    const categories = await categoriesRes.json();
    const brands = await brandsRes.json();
    const topProducts = await topProductsRes.json();
    const alerts = await alertsRes.json();
    const metadata = await metadataRes.json();

    // Update header metadata
    if (metadata && metadata.store_name) {
      const storeNameEl = document.getElementById("store-name");
      const uploadDateEl = document.getElementById("upload-date");
      const storeMetaEl = document.getElementById("store-metadata");
      if (storeNameEl) storeNameEl.textContent = metadata.store_name;
      if (uploadDateEl) uploadDateEl.textContent = metadata.upload_date;
      if (storeMetaEl) storeMetaEl.classList.remove("hidden");
    }

    // Show dashboard BEFORE rendering charts for correct canvas dimensions
    document.getElementById("loading-state").classList.add("hidden");
    document.getElementById("dashboard-content").classList.remove("hidden");

    renderKPIs(kpis);
    renderStockStatus(stockStatus);
    renderSuppliersChart(suppliers);
    renderCategoriesChart(categories);
    renderBrandsChart(brands);
    renderTopProductsTable(topProducts);
    renderAlertsTable(alerts);
    populateCategoryFilter(categories);
    populateBrandFilter();

    updateStatus(true, `${formatNumber(kpis.total_skus)} productos`);

    // Initial search
    searchProducts(1);
    return true;
  } catch (error) {
    console.error("Error loading data:", error);
    updateStatus(false, "Error al cargar datos");
    document.getElementById("loading-state").innerHTML = `
      <div class="text-center">
        <div class="text-6xl mb-4">⚠️</div>
        <h3 class="text-xl font-semibold text-gray-300 mb-2">No se pudo cargar los datos</h3>
        <p class="text-slate-500 mb-4">${error.message || 'Error de conexión con el servidor'}</p>
        <button onclick="loadData()" class="px-6 py-2 bg-[#0c4a6e] hover:bg-[#0a3d5c] rounded-lg text-white font-medium">
          Reintentar
        </button>
      </div>
    `;
    return false;
  }
}

// ==================== RENDER KPIs ====================

function renderKPIs(kpis) {
  const grid = document.getElementById("kpi-grid");
  if (!grid) return;

  const kpiCards = [
    {
      label: "Valor Total",
      value: formatCurrency(kpis.total_value),
      subtitle: "Inversión en inventario",
      icon: "💰",
      bg: "bg-emerald-100",
    },
    {
      label: "Total SKUs",
      value: formatNumber(kpis.total_skus),
      subtitle: `${formatNumber(kpis.active_skus)} SKUs con stock`,
      icon: "📦",
      bg: "bg-blue-100",
    },
    {
      label: "Stock Total",
      value: formatNumber(kpis.total_stock),
      subtitle: `Promedio: ${kpis.avg_stock} uds/SKU`,
      icon: "📊",
      bg: "bg-purple-100",
    },
    {
      label: "Alertas",
      value: formatNumber(kpis.alerts.total_alerts),
      subtitle: `${formatNumber(kpis.alerts.out_of_stock)} productos sin stock`,
      icon: "⚠️",
      bg: "bg-amber-100",
    },
    {
      label: "Diferencias",
      value: formatNumber(kpis.diferencias_count),
      subtitle: `${formatNumber(kpis.diferencias_count)} SKUs afectados`,
      icon: "🔻",
      bg: "bg-red-100",
    },
    {
      label: "Valorizado Negativo",
      value: formatCurrency(Math.abs(kpis.diferencias_value)),
      subtitle: `${formatNumber(Math.abs(kpis.diferencias_units))} unidades`,
      icon: "💸",
      bg: "bg-rose-100",
    },
  ];

  grid.innerHTML = kpiCards
    .map(
      (kpi) => `
      <div class="card">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs text-slate-500 mb-1 uppercase tracking-wide">${kpi.label}</p>
            <p class="text-2xl font-semibold text-[#0c4a6e]">${kpi.value}</p>
            ${kpi.subtitle ? `<p class="text-xs text-slate-400 mt-1">${kpi.subtitle}</p>` : ""}
          </div>
          <div class="w-10 h-10 ${kpi.bg} rounded-lg flex items-center justify-center text-xl">
            ${kpi.icon}
          </div>
        </div>
      </div>
    `
    )
    .join("");
}

// ==================== RENDER STOCK STATUS ====================

function renderStockStatus(data) {
  const panel = document.getElementById("stock-status-panel");
  if (!panel) return;

  panel.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      ${data
        .map(
          (item) => `
        <div class="stock-status-card text-center p-3 rounded-lg bg-slate-50 border-2 border-slate-200 cursor-pointer hover:shadow-md hover:border-[#38bdf8] hover:bg-sky-50 transition-all"
             data-status="${item.status}"
             onclick="filterByStatus('${item.status}')">
          <div class="text-2xl mb-1">${item.icon}</div>
          <p class="text-xl font-semibold text-[#0c4a6e]">${formatNumber(item.count)}</p>
          <p class="text-xs text-slate-500">${item.label}</p>
          <p class="text-xs font-medium" style="color: ${item.color}">${item.percentage}%</p>
        </div>
      `
        )
        .join("")}
    </div>
    <div class="mt-4">
      <div class="flex h-2 rounded-full overflow-hidden bg-slate-200">
        ${data
          .map(
            (item) => `
          <div class="status-bar" style="width: ${item.percentage}%; background-color: ${item.color};"
               title="${item.label}: ${item.count} productos"></div>
        `
          )
          .join("")}
      </div>
    </div>
  `;
}

// Filter by status (interactive stock cards)
function filterByStatus(status) {
  const select = document.getElementById("filter-status");
  if (!select) return;

  // Toggle: si ya está seleccionado, deseleccionar
  if (select.value === status) {
    select.value = "";
  } else {
    select.value = status;
  }

  // Resaltar tarjeta activa
  document.querySelectorAll(".stock-status-card").forEach((card) => {
    if (card.dataset.status === select.value) {
      card.classList.add("border-[#38bdf8]", "bg-sky-50", "shadow-md");
      card.classList.remove("border-slate-200", "bg-slate-50");
    } else {
      card.classList.remove("border-[#38bdf8]", "bg-sky-50", "shadow-md");
      card.classList.add("border-slate-200", "bg-slate-50");
    }
  });
  searchProducts(1);
}

// ==================== CHARTS ====================

function renderSuppliersChart(data) {
  const ctx = document.getElementById("suppliers-chart");
  if (!ctx) return;

  if (suppliersChart) suppliersChart.destroy();

  const topSuppliers = data.slice(0, 8);

  suppliersChart = new Chart(ctx.getContext("2d"), {
    type: "bar",
    data: {
      labels: topSuppliers.map((d) => d.supplier.substring(0, 15)),
      datasets: [
        {
          label: "Valor (S/)",
          data: topSuppliers.map((d) => d.value),
          backgroundColor: "#0c4a6e",
          borderWidth: 0,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          titleColor: "#f8fafc",
          bodyColor: "#e2e8f0",
          borderColor: "rgba(148, 163, 184, 0.2)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
          callbacks: {
            label: (context) => {
              const item = topSuppliers[context.dataIndex];
              return ` ${formatCurrency(item.value)} - ${item.products} productos`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { callback: (value) => formatCurrency(value), color: "#64748b" },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#334155", font: { size: 11 } },
        },
      },
    },
  });
}

function renderCategoriesChart(data) {
  const container = document.getElementById("categories-chart-container");
  if (!container) return;

  if (categoriesChart) categoriesChart.destroy();

  const allData = data;
  const chartHeight = Math.max(280, allData.length * 40);

  // Create wrapper div to force height for scrolling
  container.innerHTML = `<div style="height: ${chartHeight}px; min-height: ${chartHeight}px;"><canvas id="categories-chart"></canvas></div>`;

  const ctx = document.getElementById("categories-chart").getContext("2d");

  categoriesChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: allData.map((d) => d.category.substring(0, 12)),
      datasets: [
        {
          label: "Valor (S/)",
          data: allData.map((d) => d.value),
          backgroundColor: "#f97316",
          borderWidth: 0,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          titleColor: "#f8fafc",
          bodyColor: "#e2e8f0",
          borderColor: "rgba(148, 163, 184, 0.2)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (context) => `Valor: ${formatCurrency(context.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(203, 213, 225, 0.3)", drawBorder: false },
          ticks: { color: "#94a3b8", font: { size: 11 }, callback: (value) => formatCurrency(value) },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#64748b", font: { size: 11 } },
        },
      },
    },
  });
}

function renderBrandsChart(data) {
  const ctx = document.getElementById("brands-chart");
  if (!ctx) return;

  if (brandsChart) brandsChart.destroy();

  const topData = data.slice(0, 10);

  brandsChart = new Chart(ctx.getContext("2d"), {
    type: "bar",
    data: {
      labels: topData.map((d) => d.brand.substring(0, 15)),
      datasets: [
        {
          label: "Valor (S/)",
          data: topData.map((d) => d.value),
          backgroundColor: "#22c55e",
          borderWidth: 0,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.95)",
          titleColor: "#f8fafc",
          bodyColor: "#e2e8f0",
          borderColor: "rgba(148, 163, 184, 0.2)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (context) => `Valor: ${formatCurrency(context.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#64748b", font: { size: 10 } },
        },
        y: {
          grid: { color: "rgba(203, 213, 225, 0.3)", drawBorder: false },
          ticks: { color: "#94a3b8", font: { size: 11 }, callback: (value) => formatCurrency(value) },
        },
      },
    },
  });
}

// ==================== TABLES ====================

function renderTopProductsTable(data) {
  const container = document.getElementById("top-products-table");
  if (!container) return;

  container.innerHTML = `
    <table class="w-full text-sm">
      <thead class="text-slate-500 border-b border-slate-200">
        <tr>
          <th class="text-left py-2 px-2">Producto</th>
          <th class="text-right py-2 px-2">Stock</th>
          <th class="text-right py-2 px-2">Valor</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        ${data
          .slice(0, 10)
          .map(
            (item) => `
          <tr class="hover:bg-slate-50">
            <td class="py-2 px-2">
              <p class="text-slate-700 truncate max-w-[200px]" title="${item.product}">${item.product}</p>
              <p class="text-xs text-slate-400">${item.category}</p>
            </td>
            <td class="text-right py-2 px-2 text-slate-600">${formatNumber(item.stock)}</td>
            <td class="text-right py-2 px-2 text-[#0c4a6e] font-medium">${formatCurrency(item.value)}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderAlertsTable(data) {
  const container = document.getElementById("alerts-table");
  if (!container) return;

  container.innerHTML = `
    <table class="w-full text-sm">
      <thead class="text-slate-500 border-b border-slate-200">
        <tr>
          <th class="text-left py-2 px-2">Estado</th>
          <th class="text-left py-2 px-2">Producto</th>
          <th class="text-right py-2 px-2">Stock</th>
          <th class="text-right py-2 px-2">Valor</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        ${data
          .slice(0, 15)
          .map(
            (item) => `
          <tr class="hover:bg-slate-50">
            <td class="py-2 px-2">${getStatusBadge(item.status)}</td>
            <td class="py-2 px-2">
              <p class="text-slate-700 truncate max-w-[180px]" title="${item.product}">${item.product}</p>
              <p class="text-xs text-slate-400">${item.category}</p>
            </td>
            <td class="text-right py-2 px-2 font-mono ${item.stock < 0 ? "text-red-500" : "text-slate-600"}">${item.stock}</td>
            <td class="text-right py-2 px-2 text-slate-600">${formatCurrency(item.value)}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

// ==================== SEARCH & FILTERS ====================

function populateCategoryFilter(categories) {
  const select = document.getElementById("filter-category");
  if (!select) return;
  select.innerHTML = '<option value="">Todas las categorías</option>';
  categories.forEach((cat) => {
    select.innerHTML += `<option value="${cat.category}">${cat.category}</option>`;
  });
}

async function populateBrandFilter() {
  const category = document.getElementById("filter-category")?.value || "";
  const brandSelect = document.getElementById("filter-brand");
  if (!brandSelect) return;

  try {
    const response = await fetch(
      `${API_URL}/unique-brands?category=${encodeURIComponent(category)}`,
      { credentials: "include" }
    );
    const brands = await response.json();

    const currentVal = brandSelect.value;
    brandSelect.innerHTML = '<option value="">Todas las marcas</option>';
    brands.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b;
      opt.textContent = b === "SIN_MARCA" ? "(Sin Marca)" : b;
      brandSelect.appendChild(opt);
    });

    if (brands.includes(currentVal)) {
      brandSelect.value = currentVal;
    }
  } catch (e) {
    console.error("Error fetching brands", e);
  }
}

// Build multi-sort string
function getActiveSorts() {
  const sorts = [];
  const dateSort = document.getElementById("sort-date")?.value;
  const stockSort = document.getElementById("sort-stock")?.value;
  const valueSort = document.getElementById("sort-value")?.value;
  if (dateSort) sorts.push(dateSort);
  if (stockSort) sorts.push(stockSort);
  if (valueSort) sorts.push(valueSort);
  return sorts.join(",");
}

function getItemsPerPage() {
  const select = document.getElementById("items-per-page");
  return select ? parseInt(select.value) : 20;
}

async function searchProducts(page = 1) {
  currentPage = page;
  const query = document.getElementById("search-input")?.value || "";
  const category = document.getElementById("filter-category")?.value || "";
  const brand = document.getElementById("filter-brand")?.value || "";
  const status = document.getElementById("filter-status")?.value || "";
  const sort = getActiveSorts();
  const limit = getItemsPerPage();

  try {
    const params = new URLSearchParams();
    if (query) params.append("q", query);
    if (category) params.append("category", category);
    if (brand) params.append("brand", brand);
    if (status) params.append("status", status);
    if (sort) params.append("sort", sort);
    params.append("page", page);
    params.append("limit", limit);

    const response = await fetch(`${API_URL}/search?${params}`, {
      credentials: "include",
    });
    const data = await response.json();

    renderSearchResults(data);
    renderPagination(data.total);
  } catch (error) {
    console.error("Search error:", error);
  }
}

function renderSearchResults(data) {
  const container = document.getElementById("search-results");
  if (!container) return;

  if (data.results.length === 0) {
    container.innerHTML = `
      <div class="text-center py-8 text-slate-500">
        <p>No se encontraron productos</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <p class="text-sm text-slate-500 mb-4">Mostrando ${data.showing} de ${formatNumber(data.total)} productos</p>
    <table class="w-full text-sm">
      <thead class="text-slate-500 border-b border-slate-200">
        <tr>
          <th class="text-left py-2 px-3">Fecha</th>
          <th class="text-left py-2 px-3">SKU</th>
          <th class="text-left py-2 px-3">Producto</th>
          <th class="text-left py-2 px-3">Categoría</th>
          <th class="text-left py-2 px-3">Marca</th>
          <th class="text-right py-2 px-3">Stock</th>
          <th class="text-right py-2 px-3">Valor</th>
          <th class="text-center py-2 px-3">Estado</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100">
        ${data.results
          .map(
            (item) => `
          <tr class="hover:bg-slate-50">
            <td class="py-2 px-3 text-slate-500 text-xs">${item.created_at || "-"}</td>
            <td class="py-2 px-3 text-slate-500 font-mono text-xs">${item.sku}</td>
            <td class="py-2 px-3 text-slate-700">${item.product}</td>
            <td class="py-2 px-3 text-slate-500">${item.category}</td>
            <td class="py-2 px-3">${getBrandBadge(item.brand)}</td>
            <td class="py-2 px-3 text-right ${item.stock < 0 ? "text-red-500" : "text-slate-600"} font-mono">${formatNumber(item.stock)}</td>
            <td class="py-2 px-3 text-right text-[#0c4a6e] font-medium">${formatCurrency(item.value)}</td>
            <td class="py-2 px-3 text-center">${getStatusBadge(item.status)}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderPagination(total) {
  const container = document.getElementById("pagination-container");
  const buttonsDiv = document.getElementById("pagination-buttons");
  const infoP = document.getElementById("results-info");
  if (!container || !buttonsDiv || !infoP) return;

  if (total === 0) {
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");
  const itemsPerPage = getItemsPerPage();
  const totalPages = Math.ceil(total / itemsPerPage);
  const start = (currentPage - 1) * itemsPerPage + 1;
  const end = Math.min(currentPage * itemsPerPage, total);

  infoP.textContent = `Mostrando ${start}-${end} de ${formatNumber(total)}`;

  let buttons = "";
  buttons += `<button class="pagination-btn" ${currentPage === 1 ? "disabled" : ""} onclick="searchProducts(${currentPage - 1})">Anterior</button>`;

  const maxVisible = 5;
  let startPage = Math.max(1, currentPage - 2);
  let endPage = Math.min(totalPages, startPage + maxVisible - 1);

  if (startPage > 1)
    buttons += `<button class="pagination-btn" onclick="searchProducts(1)">1</button>`;
  if (startPage > 2)
    buttons += `<span class="px-2 text-slate-400">...</span>`;

  for (let i = startPage; i <= endPage; i++) {
    buttons += `<button class="pagination-btn ${i === currentPage ? "active" : ""}" onclick="searchProducts(${i})">${i}</button>`;
  }

  if (endPage < totalPages - 1)
    buttons += `<span class="px-2 text-slate-400">...</span>`;
  if (endPage < totalPages)
    buttons += `<button class="pagination-btn" onclick="searchProducts(${totalPages})">${totalPages}</button>`;

  buttons += `<button class="pagination-btn" ${currentPage === totalPages ? "disabled" : ""} onclick="searchProducts(${currentPage + 1})">Siguiente</button>`;

  buttonsDiv.innerHTML = buttons;
}

// ==================== HELPERS ====================

function getBrandBadge(brand) {
  if (!brand || brand === "nan" || brand === "None" || brand.trim() === "") {
    return '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-400 italic">Sin marca</span>';
  }
  return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-700">${brand}</span>`;
}

function getStatusBadge(status) {
  const badges = {
    negative:
      '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">🔴 Negativo</span>',
    out_of_stock:
      '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-700">🟠 Sin Stock</span>',
    critical:
      '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-700">🟡 Crítico</span>',
    low: '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-lime-100 text-lime-700">🟢 Bajo</span>',
    optimal:
      '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-700">🟢 Óptimo</span>',
    overstock:
      '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-700">🔵 Exceso</span>',
  };
  return badges[status] || status;
}

// ==================== INITIALIZE ====================

document.addEventListener("DOMContentLoaded", async () => {
  // Set dynamic year
  const yearEl = document.getElementById("current-year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Event listener for search input (Enter key)
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") searchProducts(1);
    });
  }

  // Check if server has data loaded already
  try {
    const healthRes = await fetch(`${API_URL}/health`, { credentials: "include" });
    const health = await healthRes.json();
    if (health.data_loaded) {
      loadData();
    }
  } catch (e) {
    // Server not available, show empty state
  }
});
