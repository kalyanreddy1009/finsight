import { request } from "./client";
import type { Category } from "./types";

export async function listCategories(): Promise<Category[]> {
  const { data } = await request<Category[]>("GET", "/categories");
  return data;
}
