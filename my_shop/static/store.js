const CART_KEY = 'myshop_cart';
const WISHLIST_KEY = 'myshop_wishlist';

function getCart() {
  return JSON.parse(localStorage.getItem(CART_KEY) || '[]');
}

function saveCart(items) {
  localStorage.setItem(CART_KEY, JSON.stringify(items));
  updateCartBadge();
}

function addToCart(product, qty = 1) {
  const cart = getCart();
  const found = cart.find((item) => item.id === product.id);
  if (found) {
    found.qty += qty;
  } else {
    cart.push({ ...product, qty });
  }
  saveCart(cart);
}

function removeFromCart(productId) {
  const cart = getCart().filter((item) => item.id !== productId);
  saveCart(cart);
}

function updateQty(productId, nextQty) {
  const cart = getCart();
  const item = cart.find((entry) => entry.id === productId);
  if (!item) return;
  if (nextQty <= 0) {
    removeFromCart(productId);
    return;
  }
  item.qty = nextQty;
  saveCart(cart);
}

function cartTotalQty() {
  return getCart().reduce((sum, item) => sum + item.qty, 0);
}

function cartTotalPrice() {
  return getCart().reduce((sum, item) => sum + item.price * item.qty, 0);
}

function updateCartBadge() {
  const count = cartTotalQty();
  document.querySelectorAll('[data-cart-badge]').forEach((badge) => {
    badge.textContent = count;
    badge.classList.toggle('d-none', count === 0);
  });
}

function getWishlist() {
  return JSON.parse(localStorage.getItem(WISHLIST_KEY) || '[]');
}

function toggleWishlist(product) {
  const wishlist = getWishlist();
  const found = wishlist.find((item) => item.id === product.id);
  let updated;
  if (found) {
    updated = wishlist.filter((item) => item.id !== product.id);
  } else {
    updated = [...wishlist, product];
  }
  localStorage.setItem(WISHLIST_KEY, JSON.stringify(updated));
  return !found;
}

function isWishlist(productId) {
  return getWishlist().some((item) => item.id === productId);
}

document.addEventListener('DOMContentLoaded', updateCartBadge);
