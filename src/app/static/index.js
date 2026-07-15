// App State
let sarees = [];
let selectedSaree = null;
let currentView = 'catalog'; // 'catalog', 'admin-login', 'admin-dashboard'
let adminToken = localStorage.getItem('admin_token') || '';
let whatsappPhone = '919876543210'; // Fallback default
let isEditing = false;
let editingSareeId = null;
let currentPromoDiscount = 0;
let currentPromoCode = '';

// DOM Elements
const viewCatalog = document.getElementById('view-catalog');
const viewAdminLogin = document.getElementById('view-admin-login');
const viewAdminDashboard = document.getElementById('view-admin-dashboard');
const btnAdminNav = document.getElementById('btn-admin-nav');
const btnCatalogNav = document.getElementById('btn-catalog-nav');
const sareeGrid = document.getElementById('saree-grid');
const searchInput = document.getElementById('search-fabric');
const searchColor = document.getElementById('search-color');
const filterStatus = document.getElementById('filter-status');
const minPriceInput = document.getElementById('min-price');
const maxPriceInput = document.getElementById('max-price');

// Modals
const modalProduct = document.getElementById('modal-product');
const modalAddSaree = document.getElementById('modal-add-saree');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  fetchConfigs();
  fetchSarees();
  setupRouting();
  setupEventListeners();
});

// Fetch Configs
async function fetchConfigs() {
  try {
    // Check if we can get configs, else keep defaults
    const res = await fetch('/api/v1/sarees/config');
    if (res.ok) {
      const data = await res.json();
      whatsappPhone = data.whatsapp_phone;
      if (data.project_name) {
        document.title = data.project_name;
        // Keep full name representation
        document.querySelector('.logo-group h1').innerText = data.project_name.replace(" Saree Platform", "");
      }
    }
  } catch (e) {
    console.log("Config fetch skipped, using defaults.");
  }
}

// Fetch Saree Listings
async function fetchSarees() {
  try {
    let query = `/api/v1/sarees/?`;
    const fabric = searchInput.value;
    const color = searchColor.value;
    const status = filterStatus.value;
    const minPrice = minPriceInput.value;
    const maxPrice = maxPriceInput.value;

    if (fabric) query += `fabric=${encodeURIComponent(fabric)}&`;
    if (color) query += `color=${encodeURIComponent(color)}&`;
    if (status) query += `status_filter=${encodeURIComponent(status)}&`;
    if (minPrice) query += `min_price=${encodeURIComponent(minPrice)}&`;
    if (maxPrice) query += `max_price=${encodeURIComponent(maxPrice)}&`;

    const res = await fetch(query);
    if (res.ok) {
      sarees = await res.json();
      renderSarees();
    }
  } catch (e) {
    showToast("Error loading sarees. Please try again.");
  }
}

// Render Sarees to Grid
function renderSarees() {
  sareeGrid.innerHTML = '';
  if (sarees.length === 0) {
    sareeGrid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #888;">
        <h3>No sarees found matching your filters.</h3>
        <p>Try clearing your filters to see other products.</p>
      </div>
    `;
    return;
  }

  sarees.forEach(saree => {
    const statusText = saree.status.replace('_', ' ');
    const card = document.createElement('div');
    card.className = 'saree-card';
    card.onclick = () => openSareeDetail(saree.id);
    
    card.innerHTML = `
      <div class="card-img-wrapper">
        <span class="status-badge ${saree.status}">${statusText}</span>
        <img src="${saree.image_url}" alt="${saree.title}">
      </div>
      <div class="card-body">
        <span class="card-fabric">${saree.fabric}</span>
        <h3 class="card-title">${saree.title}</h3>
        <div class="card-meta">
          <span class="card-price">₹${parseFloat(saree.price).toLocaleString('en-IN')}</span>
          <button class="btn-card-action">View Details</button>
        </div>
      </div>
    `;
    sareeGrid.appendChild(card);
  });
}

// Open Saree Details Modal
async function openSareeDetail(sareeId) {
  try {
    const res = await fetch(`/api/v1/sarees/${sareeId}`);
    if (res.ok) {
      selectedSaree = await res.json();
      
      // Update DOM
      document.getElementById('modal-img').src = selectedSaree.image_url;
      document.getElementById('modal-title').innerText = selectedSaree.title;
      document.getElementById('modal-fabric').innerText = selectedSaree.fabric;
      document.getElementById('modal-color').innerText = selectedSaree.color;
      document.getElementById('modal-status').innerText = selectedSaree.status.replace('_', ' ').toUpperCase();
      document.getElementById('modal-desc').innerText = selectedSaree.description;
      
      // Reset Promo Code State
      document.getElementById('promo-input').value = '';
      document.getElementById('promo-message').innerText = '';
      document.getElementById('promo-message').style.color = 'inherit';
      currentPromoDiscount = 0;
      currentPromoCode = '';

      // Update Dynamic Price, WhatsApp link, and UPI QR Code
      updateModalPriceAndLink();
      
      // Activate Modal
      modalProduct.classList.add('active');
      
      // Record click asynchronously
      fetch(`/api/v1/sarees/${sareeId}/click`, { method: 'POST' });
    }
  } catch (e) {
    showToast("Failed to fetch product details.");
  }
}

// Update Modal Price & UPI QR Code dynamically based on discount
function updateModalPriceAndLink() {
  if (!selectedSaree) return;

  const originalPrice = parseFloat(selectedSaree.price);
  const discountAmount = originalPrice * currentPromoDiscount;
  const finalPrice = originalPrice - discountAmount;

  // Render price display
  const priceDisplay = document.getElementById('modal-price');
  if (currentPromoDiscount > 0) {
    priceDisplay.innerHTML = `
      <span style="text-decoration: line-through; color: #888; font-size: 1.2rem; margin-right: 0.5rem;">
        ₹${originalPrice.toLocaleString('en-IN')}
      </span>
      <span>₹${finalPrice.toLocaleString('en-IN')}</span>
      <span style="font-size: 0.85rem; color: var(--success-green); font-weight: 600; margin-left: 0.5rem;">
        (${Math.round(currentPromoDiscount * 100)}% OFF)
      </span>
    `;
  } else {
    priceDisplay.innerText = `₹${originalPrice.toLocaleString('en-IN')}`;
  }

  // Handle WhatsApp Link & Pre-Booking
  const isSoldOut = selectedSaree.status === 'sold_out';
  const btnWaText = document.getElementById('wa-btn-text');
  
  let msg = '';
  if (isSoldOut) {
    btnWaText.innerText = "Join Waitlist / Pre-Book";
    msg = `Hi! The saree "${selectedSaree.title}" (ID: ${selectedSaree.id}) is Sold Out. I'd like to join the waitlist and pre-book it. Please notify me when it is back in stock!`;
  } else {
    btnWaText.innerText = "Order via WhatsApp";
    msg = `Hi! I want to order your saree: "${selectedSaree.title}" (ID: ${selectedSaree.id}).\n`;
    if (currentPromoCode) {
      msg += `Promo Code Applied: ${currentPromoCode} (${Math.round(currentPromoDiscount * 100)}% OFF)\n`;
      msg += `Original Price: ₹${originalPrice.toLocaleString('en-IN')}\n`;
      msg += `Discounted Price: ₹${finalPrice.toLocaleString('en-IN')}\n`;
    } else {
      msg += `Price: ₹${originalPrice.toLocaleString('en-IN')}\n`;
    }
    msg += `Please hold this item for me. (Note: 30-min cart reservation holds apply)`;
  }

  const waLink = `https://wa.me/${whatsappPhone}?text=${encodeURIComponent(msg)}`;
  const btnWa = document.getElementById('btn-wa-order');
  btnWa.href = waLink;
  btnWa.target = '_blank';

  // Handle UPI QR Code Section
  const upiSection = document.getElementById('upi-payment-section');
  if (isSoldOut) {
    upiSection.style.display = 'none';
  } else {
    upiSection.style.display = 'block';
    // Format merchant UPI url: pay to owner's VPA
    const upiAddress = 'owner@okaxis'; // replace with business UPI id
    const upiUrl = `upi://pay?pa=${upiAddress}&pn=ZariSarees&am=${finalPrice.toFixed(2)}&tn=Order_${selectedSaree.id.substring(0,8)}`;
    document.getElementById('upi-qr').src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(upiUrl)}`;
  }
}

// Apply Coupon Code
function applyPromoCode() {
  const code = document.getElementById('promo-input').value.trim().toUpperCase();
  const messageSpan = document.getElementById('promo-message');

  if (!code) {
    messageSpan.innerText = "Please enter a coupon code.";
    messageSpan.style.color = "red";
    return;
  }

  // Pre-configured coupons
  if (code === 'WELCOME10') {
    currentPromoDiscount = 0.10;
    currentPromoCode = 'WELCOME10';
    messageSpan.innerText = "WELCOME10 applied! 10% discount added.";
    messageSpan.style.color = "var(--success-green)";
  } else if (code === 'ZARI20') {
    currentPromoDiscount = 0.20;
    currentPromoCode = 'ZARI20';
    messageSpan.innerText = "ZARI20 applied! Special 20% discount added.";
    messageSpan.style.color = "var(--success-green)";
  } else {
    messageSpan.innerText = "Invalid coupon code.";
    messageSpan.style.color = "red";
    currentPromoDiscount = 0;
    currentPromoCode = '';
  }

  updateModalPriceAndLink();
}

// Close Product Modal
function closeProductModal() {
  modalProduct.classList.remove('active');
}

// Navigation & Routing Setup
function setupRouting() {
  if (adminToken) {
    showView('admin-dashboard');
  } else {
    showView('catalog');
  }
}

function showView(view) {
  currentView = view;
  viewCatalog.style.display = view === 'catalog' ? 'block' : 'none';
  viewAdminLogin.style.display = view === 'admin-login' ? 'block' : 'none';
  viewAdminDashboard.style.display = view === 'admin-dashboard' ? 'block' : 'none';

  if (view === 'admin-dashboard') {
    btnAdminNav.innerText = "Log Out";
    btnCatalogNav.style.display = "block";
    loadAdminDashboard();
  } else if (view === 'admin-login') {
    btnAdminNav.innerText = "Customer Site";
    btnCatalogNav.style.display = "none";
  } else {
    btnAdminNav.innerText = "Admin Portal";
    btnCatalogNav.style.display = "none";
  }
}

// Admin Operations
async function loadAdminDashboard() {
  await fetchAnalytics();
  await loadAdminSareeTable();
}

async function fetchAnalytics() {
  try {
    const res = await fetch('/api/v1/admin/analytics', {
      headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      document.getElementById('stat-total-sarees').innerText = data.total_sarees;
      document.getElementById('stat-in-stock').innerText = data.status_breakdown.in_stock || 0;
      document.getElementById('stat-sold-out').innerText = data.status_breakdown.sold_out || 0;

      // Popular list
      const popularList = document.getElementById('popular-list');
      popularList.innerHTML = '';
      if (data.popular_sarees.length === 0) {
        popularList.innerHTML = '<li>No views recorded yet.</li>';
      } else {
        data.popular_sarees.forEach(item => {
          popularList.innerHTML += `
            <li>
              <strong>${item.title}</strong> (${item.fabric}) - 
              <span style="color:#C5A059; font-weight:600;">${item.clicks} views</span>
            </li>
          `;
        });
      }
    } else if (res.status === 401) {
      logoutAdmin();
    }
  } catch (e) {
    showToast("Failed to fetch analytics.");
  }
}

async function loadAdminSareeTable() {
  try {
    const res = await fetch('/api/v1/sarees/');
    if (res.ok) {
      const allSarees = await res.ok ? await res.json() : [];
      const tbody = document.getElementById('admin-saree-tbody');
      tbody.innerHTML = '';

      if (allSarees.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">No sarees in catalog. Click '+' to add.</td></tr>`;
        return;
      }

      allSarees.forEach(saree => {
        tbody.innerHTML += `
          <tr>
            <td><img src="${saree.image_url}" style="width:40px; height:50px; object-fit:cover; border-radius:3px;"></td>
            <td><strong>${saree.title}</strong></td>
            <td>${saree.fabric}</td>
            <td>₹${parseFloat(saree.price).toLocaleString('en-IN')}</td>
            <td>
              <select onchange="updateSareeStatus('${saree.id}', this.value)" class="form-control" style="padding:0.25rem 0.5rem; width:120px;">
                <option value="in_stock" ${saree.status === 'in_stock' ? 'selected' : ''}>In Stock</option>
                <option value="low_stock" ${saree.status === 'low_stock' ? 'selected' : ''}>Low Stock</option>
                <option value="sold_out" ${saree.status === 'sold_out' ? 'selected' : ''}>Sold Out</option>
              </select>
            </td>
            <td>
              <div class="action-btns">
                <button class="btn-sm btn-edit" onclick="editSareeClick('${saree.id}')">Edit</button>
                <button class="btn-sm btn-delete" onclick="deleteSareeClick('${saree.id}')">Delete</button>
              </div>
            </td>
          </tr>
        `;
      });
    }
  } catch (e) {
    showToast("Failed to load inventory table.");
  }
}

// Update saree status directly
async function updateSareeStatus(sareeId, newStatus) {
  try {
    const res = await fetch(`/api/v1/sarees/${sareeId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${adminToken}`
      },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      showToast("Stock status updated successfully!");
      loadAdminDashboard();
    } else {
      showToast("Failed to update status.");
    }
  } catch (e) {
    showToast("Server communication error.");
  }
}

// Edit saree button trigger
async function editSareeClick(sareeId) {
  try {
    const res = await fetch(`/api/v1/sarees/${sareeId}`);
    if (res.ok) {
      const saree = await res.json();
      isEditing = true;
      editingSareeId = sareeId;
      
      document.getElementById('form-title').value = saree.title;
      document.getElementById('form-fabric').value = saree.fabric;
      document.getElementById('form-color').value = saree.color;
      document.getElementById('form-price').value = saree.price;
      document.getElementById('form-image-url').value = saree.image_url;
      document.getElementById('form-description').value = saree.description;
      
      document.getElementById('saree-modal-title').innerText = "Edit Saree Listing";
      modalAddSaree.classList.add('active');
    }
  } catch (e) {
    showToast("Could not load saree details.");
  }
}

// Delete Saree
async function deleteSareeClick(sareeId) {
  if (!confirm("Are you sure you want to delete this saree? This action cannot be undone.")) return;
  try {
    const res = await fetch(`/api/v1/sarees/${sareeId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    if (res.ok) {
      showToast("Saree listing deleted!");
      loadAdminDashboard();
    } else {
      showToast("Failed to delete saree.");
    }
  } catch (e) {
    showToast("Server error.");
  }
}

// Logout
function logoutAdmin() {
  localStorage.removeItem('admin_token');
  adminToken = '';
  showView('catalog');
  showToast("Logged out successfully.");
}

// Handle Form Submission (Add / Edit)
async function handleSareeFormSubmit(event) {
  event.preventDefault();
  const payload = {
    title: document.getElementById('form-title').value,
    fabric: document.getElementById('form-fabric').value,
    color: document.getElementById('form-color').value,
    price: parseFloat(document.getElementById('form-price').value),
    image_url: document.getElementById('form-image-url').value,
    description: document.getElementById('form-description').value,
  };

  try {
    let res;
    if (isEditing) {
      res = await fetch(`/api/v1/sarees/${editingSareeId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch('/api/v1/sarees/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify(payload)
      });
    }

    if (res.ok) {
      showToast(isEditing ? "Saree updated successfully!" : "New Saree added to catalog!");
      closeAddSareeModal();
      loadAdminDashboard();
      fetchSarees(); // Refresh public list
    } else {
      const err = await res.json();
      showToast(err.detail || "Error saving saree.");
    }
  } catch (e) {
    showToast("Network error occurred.");
  }
}

// Handle image uploads
async function handleImageUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch('/api/v1/sarees/upload', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${adminToken}` },
      body: formData
    });
    if (res.ok) {
      const data = await res.json();
      document.getElementById('form-image-url').value = data.message;
      showToast("Image uploaded successfully!");
    } else {
      showToast("Image upload failed.");
    }
  } catch (e) {
    showToast("Error communicating with file upload API.");
  }
}

// Login Submit
async function handleLoginSubmit(event) {
  event.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (res.ok) {
      const data = await res.json();
      adminToken = data.access_token;
      localStorage.setItem('admin_token', adminToken);
      showView('admin-dashboard');
      showToast("Welcome back, Meera!");
    } else {
      showToast("Invalid email or password.");
    }
  } catch (e) {
    showToast("Error connecting to login server.");
  }
}

// Event Listeners
function setupEventListeners() {
  // Nav triggers
  btnAdminNav.addEventListener('click', () => {
    if (adminToken) {
      logoutAdmin();
    } else {
      showView('admin-login');
    }
  });

  btnCatalogNav.addEventListener('click', () => {
    showView('catalog');
  });

  // Search/Filters trigger
  searchInput.addEventListener('input', debounce(fetchSarees, 300));
  searchColor.addEventListener('input', debounce(fetchSarees, 300));
  filterStatus.addEventListener('change', fetchSarees);
  minPriceInput.addEventListener('input', debounce(fetchSarees, 500));
  maxPriceInput.addEventListener('input', debounce(fetchSarees, 500));

  // Forms
  document.getElementById('saree-form').addEventListener('submit', handleSareeFormSubmit);
  document.getElementById('login-form').addEventListener('submit', handleLoginSubmit);
  document.getElementById('file-upload').addEventListener('change', handleImageUpload);
  document.getElementById('btn-promo-apply').addEventListener('click', applyPromoCode);
}

// Helper: Open/Close Saree Modals
window.openAddSareeModal = () => {
  isEditing = false;
  editingSareeId = null;
  document.getElementById('saree-form').reset();
  document.getElementById('saree-modal-title').innerText = "Add New Saree Listing";
  modalAddSaree.classList.add('active');
};

window.closeAddSareeModal = () => {
  modalAddSaree.classList.remove('active');
};

window.closeProductModal = closeProductModal;

// Helper: Toast Alert
function showToast(message) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerText = message;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'none'; // reset animation
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Helper: Debounce utility
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
