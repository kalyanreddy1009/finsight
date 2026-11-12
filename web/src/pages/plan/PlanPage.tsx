import { useState } from "react";
import { listCategories } from "../../api/categories";
import { LoadError } from "../../components/LoadError";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useLoader } from "../../hooks/useLoader";
import "../../styles/plan.css";
import { AddCategoryDialog } from "./AddCategoryDialog";
import { CategoriesSection } from "./CategoriesSection";

export function PlanPage() {
  useDocumentTitle("Plan");
  const categories = useLoader(listCategories);
  const [addOpen, setAddOpen] = useState(false);
  const state = categories.state;
  return (
    <div className="plan-page">
      <header className="plan-header">
        <h1 className="title">Plan</h1>
      </header>
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
      <p className="empty-state">Budgets, recurring bills and goals are not available yet.</p>
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
