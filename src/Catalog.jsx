import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Package,
  Search,
  ShoppingBag,
} from "lucide-react";

export function ProductImage({ product, className = "" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [product.image]);
  return (
    <div className={`product-photo ${className}`}>
      {product.image && !failed ? (
        <img
          src={product.image}
          alt={product.name}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="photo-placeholder">
          <Package size={32} />
          <small>暂无图片</small>
        </span>
      )}
    </div>
  );
}

export function Pagination({ page, total, onChange }) {
  if (total <= 1) return null;
  return (
    <nav className="catalog-pagination" aria-label="翻页">
      <button
        aria-label="上一页"
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
      >
        <ChevronLeft size={17} />
      </button>
      {Array.from({ length: total }, (_, i) => i + 1)
        .filter(
          (n) =>
            total <= 8 || n === 1 || n === total || Math.abs(n - page) <= 1,
        )
        .map((n) => (
          <button
            key={n}
            aria-label={`第 ${n} 页`}
            aria-current={page === n ? "page" : undefined}
            className={page === n ? "active" : ""}
            onClick={() => onChange(n)}
          >
            {n}
          </button>
        ))}
      <button
        aria-label="下一页"
        disabled={page === total}
        onClick={() => onChange(page + 1)}
      >
        <ChevronRight size={17} />
      </button>
    </nav>
  );
}

export function Catalog({ products, globalSearch, openProduct, addCart }) {
  const [category, setCategory] = useState("全部"),
    [query, setQuery] = useState(""),
    [sort, setSort] = useState("精选排序"),
    [price, setPrice] = useState("全部价格"),
    [page, setPage] = useState(1);
  const available = products.filter((p) => p.status === "在售");
  const categories = ["全部", ...new Set(available.map((p) => p.category))];
  const term = (query || globalSearch).trim().toLowerCase();
  const filtered = available
    .filter(
      (p) =>
        (category === "全部" || p.category === category) &&
        `${p.name} ${p.brand} ${p.desc} ${p.category} ${p.id}`
          .toLowerCase()
          .includes(term) &&
        (price === "全部价格" ||
          (price === "300元以内" && p.price <= 300) ||
          (price === "300—800元" && p.price > 300 && p.price <= 800) ||
          (price === "800元以上" && p.price > 800)),
    )
    .sort((a, b) =>
      sort === "价格从低到高"
        ? a.price - b.price
        : sort === "价格从高到低"
          ? b.price - a.price
          : sort === "库存优先"
            ? b.stock - a.stock
            : 0,
    );
  const total = Math.max(1, Math.ceil(filtered.length / 12));
  const current = Math.min(page, total);
  useEffect(() => setPage(1), [category, query, globalSearch, sort, price]);
  return (
    <div className="real-catalog">
      <section className="catalog-intro">
        <div>
          <span className="catalog-eyebrow">ONDA / EVERYDAY ESSENTIALS</span>
          <h1>认真挑选，每一件好物。</h1>
          <p>从聆听、专注到轻装出行，找到适合自己的日常装备。</p>
        </div>
        <div className="catalog-count">
          <strong>{available.length}</strong>
          <span>件好物 · {categories.length - 1} 个品类</span>
        </div>
      </section>
      <div className="catalog-search-row">
        <div className="field-search">
          <Search size={19} />
          <input
            aria-label="搜索商品目录"
            placeholder="搜索品牌、型号或你需要的商品"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          aria-label="商品价格"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        >
          {["全部价格", "300元以内", "300—800元", "800元以上"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          aria-label="商品排序"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          {["精选排序", "价格从低到高", "价格从高到低", "库存优先"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </div>
      <div className="catalog-categories" aria-label="商品品类">
        {categories.map((c) => (
          <button
            className={category === c ? "active" : ""}
            key={c}
            onClick={() => setCategory(c)}
          >
            {c}
            <span>
              {c === "全部"
                ? available.length
                : available.filter((p) => p.category === c).length}
            </span>
          </button>
        ))}
      </div>
      <div className="catalog-result-heading">
        <span>
          {category === "全部" ? "全部好物" : category}
          <small>共 {filtered.length} 件</small>
        </span>
        <small>
          {current} / {total} 页
        </small>
      </div>
      <div className="real-product-grid">
        {filtered.slice((current - 1) * 12, current * 12).map((p) => (
          <article className="real-product-card" key={p.id}>
            <button
              className="real-product-image"
              aria-label={`查看${p.name}`}
              onClick={() => openProduct(p)}
            >
              <ProductImage product={p} />
              <span className="product-category-tag">{p.category}</span>
              {p.stock === 0 && (
                <span className="sold-out-label">暂时缺货</span>
              )}
            </button>
            <div className="real-product-body">
              <small className="real-product-brand">{p.brand}</small>
              <button
                className="real-product-title"
                onClick={() => openProduct(p)}
              >
                {p.name}
              </button>
              <p>{p.desc}</p>
              <div className="real-product-footer">
                <strong>
                  ¥{" "}
                  {p.price.toLocaleString("zh-CN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </strong>
                <button
                  disabled={p.stock === 0}
                  aria-label={`将${p.name}加入购物袋`}
                  onClick={() => addCart(p)}
                >
                  <ShoppingBag size={18} />
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
      {!filtered.length && (
        <div className="catalog-empty">
          <Package size={32} />
          <h3>没有找到符合条件的商品</h3>
          <p>试试其他关键词，或清除筛选条件。</p>
          <button
            onClick={() => {
              setQuery("");
              setCategory("全部");
              setPrice("全部价格");
            }}
          >
            清除筛选
          </button>
        </div>
      )}
      <Pagination
        page={current}
        total={total}
        onChange={(n) => {
          setPage(n);
          window.scrollTo({ top: 150, behavior: "smooth" });
        }}
      />
    </div>
  );
}
