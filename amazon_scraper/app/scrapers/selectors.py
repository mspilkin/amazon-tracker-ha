"""Versioned selector table.

Bump SELECTOR_VERSION whenever a selector is edited. The integration records
this per scrape and triggers a full re-scan on version change.

Each entry is a list of fallback selectors in priority order:
  1. Primary:   stable data-* attributes where Amazon provides them.
  2. Secondary: class-fragment matches robust to Amazon's hashed class suffixes.
  3. Tertiary:  text-anchored CSS or XPath for the most volatile sections.

Task 3 populates the actual selector strings. Keep this file small — it's the
one place we expect to hotfix when Amazon changes layout.
"""

from __future__ import annotations

SELECTOR_VERSION = "2026.04.16-1"

# ---- order history list page ----------------------------------------------
ORDER_CARD = [
    '[data-component="orderCard"]',
    '.order-card',
    '[class*="order-card"]',
]

ORDER_ID_IN_CARD = [
    '[data-component="orderId"] bdi',
    '.yohtmlc-order-id span:nth-of-type(2) bdi',
    'bdi',
]

ORDER_DATE_IN_CARD = [
    '[data-component="orderDate"]',
    '.order-info .a-column:nth-child(1) .value',
]

ORDER_TOTAL_IN_CARD = [
    '[data-component="orderTotal"]',
    '.order-info .a-column:nth-child(2) .value',
]

ORDER_STATUS_IN_CARD = [
    '[data-component="shipmentStatus"]',
    '.shipment-top-row .a-size-medium',
]

# ---- order detail page ----------------------------------------------------
DETAIL_ITEM_ROW = [
    '[data-component="orderItem"]',
    '.item-box',
    '[class*="item-box"]',
]

DETAIL_ITEM_TITLE = [
    'a.a-link-normal[href*="/gp/product/"]',
    'a.a-link-normal[href*="/dp/"]',
]

DETAIL_ITEM_THUMBNAIL = ['img.yo-critical-feature', 'img[class*="product-image"]']

DETAIL_ITEM_PRICE = ['.yohtmlc-item .a-color-price', '.item-price']

DETAIL_CARRIER = ['[data-component="shippingDetails"] .carrier-name']

DETAIL_TRACKING_NUMBER = ['[data-component="trackingNumber"]', '.tracking-number']

DETAIL_ETA = [
    '[data-component="promisedDeliveryDate"]',
    '.promise-date',
]

DETAIL_DELIVERY_PHOTO = ['img[alt*="Delivery photo"]', 'img.delivery-photo']

DETAIL_PAYMENT_METHOD = ['.payment-method-detail', '.pmts-portal-component']

# ---- returns page ---------------------------------------------------------
RETURN_CARD = ['[data-component="returnCard"]', '.return-item-row']
RETURN_STATUS = ['[data-component="returnStatus"]', '.return-status']
RETURN_AMOUNT = ['[data-component="refundAmount"]', '.refund-amount']
