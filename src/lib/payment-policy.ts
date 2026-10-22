export function assertWalletActionAllowed(): never {
  throw new Error("شحن الرصيد والدفع منه غير متاح؛ ادفع ثمن الطلب مباشرة.");
}
