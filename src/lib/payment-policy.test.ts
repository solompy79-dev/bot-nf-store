import { test } from "node:test";
import { strict as assert } from "node:assert";
import { assertWalletActionAllowed } from "./payment-policy";

test("wallet actions are disabled so customers pay orders directly", () => {
  assert.throws(() => assertWalletActionAllowed());
});
