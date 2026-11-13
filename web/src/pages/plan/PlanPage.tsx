import { useState } from "react";
import { listCategories } from "../../api/categories";
import { LoadError } from "../../components/LoadError";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useLoader } from "../../hooks/useLoader";
import "../../styles/plan.css";
import { AddCategoryDialog } from "./AddCategoryDialog";
import { BillsSection } from "./BillsSection";
import { BudgetSection } from "./BudgetSection";
import { CategoriesSection } from "./CategoriesSection";
import { GoalsSection } from "./GoalsSection";
import { TaxSection } from "./TaxSection";

export function PlanPage() {
  useDocumentTitle("Plan");
  const categories = useLoader(listCategories);
  const [addOpen, setAddOpen] = useState(false);
  const state = categories.state;
  // Budget and bill dialogs need the categories. They show a note until these have loaded.
  const loadedCategories = state.status === "ready" ? state.data : null;
  return (
    <div className="plan-page">
      <header className="plan-header">
        <h1 className="title">Plan</h1>
      </header>
      <BudgetSection categories={loadedCategories} />
      <BillsSection categories={loadedCategories} />
      <GoalsSection />
      <TaxSection />
      {state.status === "loading" ? (
        <p className="empty-state" role="status">
          Loading categories…
        </p>
      ) : null}
      {state.status === "error" ? (
        <LoadError message="Could not load your categories. Check your connection and try again." onRetry={categories.reload} />
      ) : null}
      {state.status === "ready" ? (
        <CategoriesSection categories={state.data} onAdd={() => setAddOpen(true)} />
      ) : null}
      <AddCategoryDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => {
          setAddOpen(false);
          categories.reload();
        }}
      />
    </div>
  );
}
