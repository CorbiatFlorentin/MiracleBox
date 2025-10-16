import { useEffect, useState } from "react";
import dayjs from "dayjs";
import "./App.css";
import "./TableStyle.css";
import "./FormStyle.css";

type Item = {
  id: number;
  name: string;
  category: string;
  perishable: boolean;
  dlc: string; // YYYY-MM-DD
  location: string;
  created_at: string;
};

type Outcome = "consomme" | "perdu";

const API = "http://localhost:8000";

/** Convertit proprement une erreur inconnue en message */
function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  try {
    return JSON.stringify(e);
  } catch {
    return "Erreur inconnue";
  }
}

export default function App() {
  const [categories, setCategories] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    category: "",
    perishable: true,
    dlc: "",
    location: "",
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Charge catégories et lieux */
  async function fetchRefs(): Promise<void> {
    const [cats, locs]: [string[], string[]] = await Promise.all([
      fetch(`${API}/categories`).then((r) => r.json()),
      fetch(`${API}/locations`).then((r) => r.json()),
    ]);
    setCategories(cats);
    setLocations(locs);
    if (!form.category && cats.length)
      setForm((f) => ({ ...f, category: cats[0] }));
    if (!form.location && locs.length)
      setForm((f) => ({ ...f, location: locs[0] }));
  }

  /** Charge les items */
  async function fetchItems(): Promise<void> {
    const data: Item[] = await fetch(`${API}/items`).then((r) => r.json());
    setItems(data);
  }

  useEffect(() => {
    void fetchRefs();
    void fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Couleur du badge selon date */
  const badge = (dlc: string): string => {
    const d = dayjs(dlc);
    const diff = d.diff(dayjs(), "day");
    if (diff < 0) return "bg-red-600 text-white";
    if (diff <= 3) return "bg-red-500 text-white";
    if (diff <= 7) return "bg-yellow-400 text-black";
    return "bg-green-500 text-white";
  };

  /** Ajout d’un article */
  async function onSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      if (!form.name.trim()) throw new Error("Nom requis");
      if (!form.dlc) throw new Error("DLC requise");

      const res = await fetch(`${API}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Erreur API");
      }

      setMessage("Article ajouté ✅");
      setTimeout(() => setMessage(null), 3000);
      setForm((f) => ({ ...f, name: "", dlc: "" }));
      await fetchItems();
    } catch (err: unknown) {
      setError(errMsg(err));
      setTimeout(() => setError(null), 3000);
    } finally {
      setLoading(false);
    }
  }

  /** Supprime un article (consommé / perdu) */
  async function disposeItem(id: number, outcome: Outcome): Promise<void> {
    setMessage(null);
    setError(null);
    try {
      const res = await fetch(`${API}/items/${id}/dispose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Erreur API");
      }
      setItems((prev) => prev.filter((it) => it.id !== id));
      setMessage(
        outcome === "consomme" ? "Marqué consommé ✅" : "Marqué perdu ❌"
      );
      setTimeout(() => setMessage(null), 3000);
    } catch (e: unknown) {
      setError(errMsg(e));
      setTimeout(() => setError(null), 3000);
    }
  }

 return (
  <>
    <div className="min-h-screen bg-neutral-900 text-white flex flex-col items-center p-10 gap-12">

      {/* --- FORMULAIRE (haut de page) --- */}
      <div className="form">
        <h1 className="text-2xl font-bold mb-4 text-center text-purple-400">
          Ajouter un article
        </h1>

        <form onSubmit={onSubmit}>
          <div className="flex-column">
            <label>Nom</label>
            <div className="inputForm">
              <input
                className="input"
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Yaourt nature"
                required
              />
            </div>
          </div>

          <div className="flex-column">
            <label>Catégorie</label>
            <div className="inputForm">
              <select
                className="input"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex-column">
            <label>Lieu</label>
            <div className="inputForm">
              <select
                className="input"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              >
                {locations.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex-row">
            <div className="flex items-center gap-2">
              <input
                id="perishable"
                type="checkbox"
                checked={form.perishable}
                onChange={(e) =>
                  setForm({ ...form, perishable: e.target.checked })
                }
              />
              <label htmlFor="perishable">Périssable</label>
            </div>
            <div className="flex-column">
              <label>DLC</label>
              <div className="inputForm">
                <input
                  className="input"
                  type="date"
                  value={form.dlc}
                  onChange={(e) => setForm({ ...form, dlc: e.target.value })}
                  required
                />
              </div>
            </div>
          </div>

          <button
            disabled={loading}
            className="button-submit"
          >
            {loading ? "Ajout..." : "Ajouter l'article"}
          </button>
        </form>
      </div>

      {/* --- TABLEAU (bas de page) --- */}
      <div className="w-full max-w-5xl">
        <h2 className="text-3xl font-semibold mb-6 text-center text-purple-400">
          Inventaire
        </h2>
        <div className="table-card">
          {items.length === 0 ? (
            <div className="text-sm text-neutral-400 text-center">
              Aucun article.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>Catégorie</th>
                    <th>Lieu</th>
                    <th>Périssable</th>
                    <th>DLC</th>
                    <th>Jours restants</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => {
                    const diff = dayjs(it.dlc).diff(dayjs(), "day");
                    return (
                      <tr key={it.id}>
                        <td>{it.name}</td>
                        <td>{it.category}</td>
                        <td>{it.location}</td>
                        <td>{it.perishable ? "Oui" : "Non"}</td>
                        <td>{dayjs(it.dlc).format("YYYY-MM-DD")}</td>
                        <td>
                          <span className={`dlc-badge ${badge(it.dlc)}`}>
                            {diff < 0 ? "Expiré" : `${diff} j`}
                          </span>
                        </td>
                        <td className="text-right">
                          <div className="flex gap-2 justify-end">
                            <button
                              className="action-btn btn-consomme"
                              onClick={() =>
                                void disposeItem(it.id, "consomme")
                              }
                            >
                              Consommé
                            </button>
                            <button
                              className="action-btn btn-perdu"
                              onClick={() =>
                                void disposeItem(it.id, "perdu")
                              }
                            >
                              Perdu
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>

    {/* --- POPUP SUCCÈS / ERREUR --- */}
    {(message || error) && (
      <div className="fixed inset-0 flex items-center justify-center bg-black/50 z-50">
        <div className="bg-neutral-800 text-center text-white px-8 py-6 rounded-2xl shadow-lg border border-purple-500 animate-fade">
          <h3
            className={`text-lg font-semibold ${
              message ? "text-green-400" : "text-red-400"
            }`}
          >
            {message || error}
          </h3>
        </div>
      </div>
    )}
  </>
);
}
