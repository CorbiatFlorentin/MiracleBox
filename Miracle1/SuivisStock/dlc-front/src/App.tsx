import { useEffect, useState } from "react";
import dayjs from "dayjs";
import "./App.css";


type Item = {
  id: number;
  name: string;
  category: string;
  perishable: boolean;
  dlc: string;        // YYYY-MM-DD
  location: string;
  created_at: string;
};

type Outcome = "consomme" | "perdu";

const API = "http://localhost:8000";

/** Convertit proprement une erreur inconnue en message */
function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  try { return JSON.stringify(e); } catch { return "Erreur inconnue"; }
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

  async function fetchRefs(): Promise<void> {
    const [cats, locs]: [string[], string[]] = await Promise.all([
      fetch(`${API}/categories`).then(r => r.json()),
      fetch(`${API}/locations`).then(r => r.json()),
    ]);
    setCategories(cats);
    setLocations(locs);
    if (!form.category && cats.length) setForm(f => ({ ...f, category: cats[0] }));
    if (!form.location && locs.length) setForm(f => ({ ...f, location: locs[0] }));
  }

  async function fetchItems(): Promise<void> {
    const data: Item[] = await fetch(`${API}/items`).then(r => r.json());
    setItems(data);
  }

  useEffect(() => {
    void fetchRefs();
    void fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const badge = (dlc: string): string => {
    const d = dayjs(dlc);
    const diff = d.diff(dayjs(), "day");
    if (diff < 0) return "bg-red-600 text-white";
    if (diff <= 3) return "bg-red-500 text-white";
    if (diff <= 7) return "bg-yellow-400 text-black";
    return "bg-green-500 text-white";
  };

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
      setForm(f => ({ ...f, name: "", dlc: "" }));
      await fetchItems();
    } catch (err: unknown) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  }

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
      // Retire localement pour feedback immédiat
      setItems(prev => prev.filter(it => it.id !== id));
      setMessage(outcome === "consomme" ? "Marqué consommé ✅" : "Marqué perdu ❌");
    } catch (e: unknown) {
      setError(errMsg(e));
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900 flex items-center">
      {/* Conteneur centré et large */}
      <div className="w-full max-w-6xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6 text-center">Suivi DLC — Stock</h1>

        {/* FORMULAIRE */}
        <form
          onSubmit={onSubmit}
          className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5 rounded-xl shadow bg-white mb-8 border border-neutral-200"
        >
          <div>
            <label className="block text-sm font-medium mb-1">Nom</label>
            <input
              className="w-full border rounded-lg px-3 py-2"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="Ex: Yaourt nature"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Catégorie</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={form.category}
              onChange={e => setForm({ ...form, category: e.target.value })}
            >
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="perishable"
              type="checkbox"
              checked={form.perishable}
              onChange={e => setForm({ ...form, perishable: e.target.checked })}
            />
            <label htmlFor="perishable" className="text-sm font-medium">Périssable</label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">DLC</label>
            <input
              type="date"
              className="w-full border rounded-lg px-3 py-2"
              value={form.dlc}
              onChange={e => setForm({ ...form, dlc: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Lieu</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={form.location}
              onChange={e => setForm({ ...form, location: e.target.value })}
            >
              {locations.map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 flex justify-center">
            <button
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-black text-white hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Ajout..." : "Ajouter l'article"}
            </button>
          </div>

          {message && <div className="md:col-span-2 text-green-700 text-center">{message}</div>}
          {error && <div className="md:col-span-2 text-red-600 text-center">{error}</div>}
        </form>

        {/* TABLEAU INVENTAIRE */}
        <div className="rounded-xl shadow bg-white p-4 border border-neutral-200">
          <h2 className="text-lg font-semibold mb-4 text-center">Inventaire</h2>
          {items.length === 0 ? (
            <div className="text-sm text-neutral-600 text-center">Aucun article.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-neutral-200">
                <thead>
                  <tr className="text-left bg-neutral-100">
                    <th className="py-2 px-3 border-b border-neutral-200">Nom</th>
                    <th className="py-2 px-3 border-b border-neutral-200">Catégorie</th>
                    <th className="py-2 px-3 border-b border-neutral-200">Lieu</th>
                    <th className="py-2 px-3 border-b border-neutral-200">Périssable</th>
                    <th className="py-2 px-3 border-b border-neutral-200">DLC</th>
                    <th className="py-2 px-3 border-b border-neutral-200">Jours restants</th>
                    <th className="py-2 px-3 border-b border-neutral-200 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(it => {
                    const diff = dayjs(it.dlc).diff(dayjs(), "day");
                    return (
                      <tr key={it.id} className="border-b border-neutral-200">
                        <td className="py-2 px-3">{it.name}</td>
                        <td className="py-2 px-3">{it.category}</td>
                        <td className="py-2 px-3">{it.location}</td>
                        <td className="py-2 px-3">{it.perishable ? "Oui" : "Non"}</td>
                        <td className="py-2 px-3">{dayjs(it.dlc).format("YYYY-MM-DD")}</td>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-1 rounded ${badge(it.dlc)}`}>
                            {diff < 0 ? "Expiré" : `${diff} j`}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          <div className="flex gap-2 justify-end">
                            <button
                              className="px-3 py-1 rounded border border-neutral-300 hover:bg-neutral-100"
                              onClick={() => void disposeItem(it.id, "consomme")}
                              title="Marquer comme consommé"
                            >
                              Consommé
                            </button>
                            <button
                              className="px-3 py-1 rounded border border-red-400 text-white bg-red-500 hover:bg-red-600"
                              onClick={() => void disposeItem(it.id, "perdu")}
                              title="Marquer comme perdu"
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
  );
}
