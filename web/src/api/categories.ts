import { request } from "./client";
import type { Category, TaxSection } from "./types";

// POST /categories body (backend/app/api/v1/schemas.py CategoryIn).
export interface CategoryBody {
  name: string;
  category_type: Category["category_type"];
  default_tax_section: TaxSection;
  is_discretionary: boolean;
  is_sensitive_private: boolean;
}

export async function listCategories(): Promise<Category[]> {
  const { data } = await request<Category[]>("GET", "/categories");
  return data;
}

export async function createCategory(body: CategoryBody): Promise<Category> {
  const { data } = await request<Category>("POST", "/categories", { body });
  return data;
}
