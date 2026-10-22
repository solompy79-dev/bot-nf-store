import { describe, it as test } from "node:test";
import { strict as assert } from "node:assert";
import { isProductPinned, nextProductOrder } from "./product-order";

describe("storefront product pinning", () => {
  test("pinning places the product before every existing product", () => {
    const orders = [0, 2, 100, -1];
    const pinnedOrder = nextProductOrder(orders, true);
    assert.equal(pinnedOrder, -2);
    assert.equal(orders.every((order) => pinnedOrder < order), true);
    assert.equal(isProductPinned(pinnedOrder), true);
  });

  test("unpinning returns the product to regular display order", () => {
    const order = nextProductOrder([-2, -1, 0, 100], false);
    assert.equal(order, 101);
    assert.equal(isProductPinned(order), false);
    assert.equal(isProductPinned(0), false);
  });
});
