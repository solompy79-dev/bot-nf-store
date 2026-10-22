import { useQuery } from "@tanstack/react-query";
import { listProducts } from "@/lib/products.functions";
import { products as staticProducts, type Product } from "@/lib/products";
import { withProductArtwork } from "./product-artwork";

export function useProducts(): Product[] {
  const { data } = useQuery({
    queryKey: ["products", "public"],
    queryFn: async () => (await listProducts()) as Product[],
    placeholderData: staticProducts,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  return (data ?? staticProducts).map(withProductArtwork);
}

export function useProduct(slug: string): Product | undefined {
  return useProducts().find((p) => p.slug === slug);
}
