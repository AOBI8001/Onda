import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  Search,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Plus,
  ShoppingBag,
  ShoppingCart,
  Package,
  Truck,
  FileText,
  Headphones,
  BarChart3,
  MessageSquare,
  Send,
  Github,
  X,
  Check,
  CheckCircle2,
  ShieldCheck,
  ShieldAlert,
  Clock3,
  LoaderCircle,
  RefreshCw,
  MoreHorizontal,
  UserRound,
  LogOut,
  SlidersHorizontal,
  Lightbulb,
  CircleHelp,
  Copy,
  Activity,
  ExternalLink,
} from "lucide-react";
import { categories } from "./data";
import "./styles.css";
import { api } from "./api";
import { LiveAgent } from "./LiveAgent";
import { DataDashboard } from "./DataDashboard";
import { Catalog, ProductImage, Pagination } from "./Catalog";

const assets = import.meta.glob("../素材图/入口页.png", {
  eager: true,
  query: "?url",
  import: "default",
});
const asset = (name) => assets[`../素材图/${name}`];
const money = (value) => `¥ ${Number(value).toLocaleString("zh-CN")}`;
const githubUrl =
  import.meta.env.VITE_GITHUB_URL || "https://github.com/AOBI8001/Onda";
function DefaultAvatar() {
  return (
    <span className="avatar default-avatar">
      <UserRound size={23} />
    </span>
  );
}
function useSaved(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const s = localStorage.getItem(key);
      return s ? JSON.parse(s) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  }, [key, value]);
  return [value, setValue];
}
function Crop({
  source = "消费者商品页.png",
  rect,
  className = "",
  label = "",
}) {
  const [x, y, w, h] = rect;
  return (
    <div
      role={label ? "img" : undefined}
      aria-label={label || undefined}
      className={`crop ${className}`}
      style={{ aspectRatio: `${w}/${h}` }}
    >
      <svg
        viewBox={`${x} ${y} ${w} ${h}`}
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <image href={asset(source)} width="1672" height="941" />
      </svg>
    </div>
  );
}
function Orb({ small = false }) {
  return <span className={`orb ${small ? "small" : ""}`} aria-hidden="true" />;
}
function Brand() {
  return (
    <a href="#/" className="brand" aria-label="Onda 返回入口">
      <span>Onda</span>
      <i />
      <small>
        A Brighter
        <br />
        Everyday
      </small>
    </a>
  );
}
function Badge({ children, tone }) {
  const color =
    tone ||
    (["高", "待确认", "待人工确认"].includes(children)
      ? "red"
      : ["在售", "已完成", "已签收", "低", "执行成功"].includes(children)
        ? "green"
        : ["处理中", "中", "草稿"].includes(children)
          ? "amber"
          : "blue");
  return (
    <span className={`badge ${color}`}>
      <span className="dot" />
      {children}
    </span>
  );
}
function Footer({ seller }) {
  return (
    <footer>
      <span>Onda — A Brighter Everyday</span>
      <span>
        {seller
          ? "更好的商业，连接更美好的生活"
          : "更 好 的 生 活，一 直 在 路 上"}
      </span>
    </footer>
  );
}
function Btn({
  children,
  onClick,
  secondary = false,
  className = "",
  ...rest
}) {
  return (
    <button
      onClick={onClick}
      className={`${secondary ? "btn-secondary" : "btn-primary"} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
function Empty({
  text = "没有找到匹配的内容",
  detail = "试试其他关键词，或清除筛选条件。",
}) {
  return (
    <div className="empty">
      <Search size={30} />
      <h3>{text}</h3>
      <p>{detail}</p>
    </div>
  );
}

function App() {
  const [route, setRoute] = useState(location.hash.slice(1) || "/");
  const role = route.startsWith("/seller") ? "seller" : "buyer";
  const [business, setBusiness] = useState({
    products: [],
    orders: [],
    tickets: [],
    audit: [],
    analytics: null,
  });
  const { products, orders, tickets, audit } = business;
  const [loadError, setLoadError] = useState("");
  const activeRole = useRef(role);
  activeRole.current = role;
  const [cart, setCart] = useSaved("onda-cart-v2", []);
  const refresh = async () => {
    try {
      const result = await api(role, "/state");
      if (activeRole.current === role) {
        setBusiness(result);
        setLoadError("");
      }
    } catch (e) {
      if (activeRole.current === role)
        setLoadError(e.message || "暂时无法连接服务，请确认后端已启动");
    }
  };
  useEffect(() => {
    setBusiness({
      products: [],
      orders: [],
      tickets: [],
      audit: [],
      analytics: null,
    });
    refresh();
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [role]);
  const [modal, setModal] = useState(null),
    [approval, setApproval] = useState(null),
    [toast, setToast] = useState(""),
    [globalSearch, setGlobalSearch] = useState(""),
    [profileOpen, setProfileOpen] = useState(false);
  useEffect(() => {
    const listener = () => {
      setRoute(location.hash.slice(1) || "/");
      setProfileOpen(false);
      setModal(null);
    };
    addEventListener("hashchange", listener);
    return () => removeEventListener("hashchange", listener);
  }, []);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 3200);
      return () => clearTimeout(t);
    }
  }, [toast]);
  const seller = route.startsWith("/seller");
  useEffect(() => {
    if (route === "/buyer/home") location.replace("#/buyer/products");
  }, [route]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route]);
  const page = route.split("/")[2] || "home";
  const go = (path) => {
    location.hash = path;
  };
  const addCart = (p) => {
    setCart((c) => {
      const old = c.find((x) => x.id === p.id);
      return old
        ? c.map((x) => (x.id === p.id ? { ...x, qty: x.qty + 1 } : x))
        : [...c, { ...p, qty: 1 }];
    });
    setToast(`${p.name} 已加入购物袋`);
  };
  const requestApproval = async (data) => {
    try {
      const proposal =
        data.proposal ||
        (await api(role, "/proposals", {
          method: "POST",
          body: {
            action: data.action,
            target: data.targetId || data.target,
            params: data.params || {},
            expected_version: data.version,
          },
        }));
      setApproval({
        ...proposal,
        description: data.description || proposal.description,
        onSuccess: data.onSuccess,
      });
    } catch (e) {
      setToast(e.message);
    }
  };
  const completeApproval = async () => {
    if (!approval) return;
    try {
      await api(role, `/proposals/${approval.id}/decision`, {
        method: "POST",
        body: { approved: true },
      });
      await refresh();
      setApproval(null);
      setModal(null);
      setToast(`${approval.title}已完成`);
      await approval.onSuccess?.();
    } catch (e) {
      setToast(e.message);
    }
  };
  const orderAction = (order, type) =>
    requestApproval({
      action: type === "refund" ? "request_refund" : "cancel_order",
      target: order.id,
      version: order.version,
      params: type === "refund" ? { reason: "消费者申请售后退款" } : {},
      description:
        type === "refund"
          ? "确认后创建退款申请，等待商家审核；此时不会退款到账。"
          : "确认后订单将被取消，无法继续发货。",
    });
  const changeProductStatus = (p) =>
    requestApproval({
      action: "set_product_status",
      target: p.id,
      version: p.version,
      params: { status: p.status === "在售" ? "下架" : "在售" },
    });
  const openProduct = (p) => setModal({ kind: "product", product: p });
  const createProduct = async (values) => {
    try {
      await api(role, "/products", { method: "POST", body: values });
      await refresh();
      setModal(null);
      setToast("已保存为商品草稿");
    } catch (e) {
      setToast(e.message);
    }
  };
  const saveProduct = (product, values) =>
    product
      ? requestApproval({
          action: "edit_product",
          target: product.id,
          version: product.version,
          params: values,
        })
      : createProduct(values);
  const core = {
    products,
    orders,
    refresh,
    createProduct,
    tickets,
    go,
    setToast,
    setModal,
    requestApproval,
    orderAction,
    changeProductStatus,
    openProduct,
    addCart,
    globalSearch,
    setGlobalSearch,
  };
  return (
    <>
      <div className={`app ${route === "/" ? "landing-app" : ""}`}>
        {route === "/" ? (
          <Landing />
        ) : (
          <>
            <header className={`header ${seller ? "merchant-header" : ""}`}>
              <Brand />
              <nav>
                {(seller
                  ? [
                      ["home", "数据看板"],
                      ["products", "商品管理"],
                      ["orders", "订单管理"],
                      ["tickets", "工单管理"],
                      ["agent", "Onda智能助手"],
                    ]
                  : [
                      ["products", "商品页"],
                      ["agent", "Onda智能助手"],
                      ["account", "个人中心"],
                    ]
                ).map(([key, label]) => (
                  <a
                    key={key}
                    className={page === key ? "active" : ""}
                    href={`#/${seller ? "seller" : "buyer"}/${key}`}
                  >
                    {label}
                  </a>
                ))}
              </nav>
              <div className="header-right">
                <form
                  className="search-bar"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!["products", "tickets", "orders"].includes(page))
                      go(`/${seller ? "seller" : "buyer"}/products`);
                  }}
                >
                  <Search size={18} />
                  <input
                    aria-label="全局搜索"
                    placeholder={
                      seller
                        ? "搜索商品、订单、工单或其他内容…"
                        : "搜索喜欢的商品…"
                    }
                    value={globalSearch}
                    onChange={(e) => setGlobalSearch(e.target.value)}
                  />
                </form>
                {!seller && (
                  <button
                    className="icon-button cart-button"
                    aria-label="打开购物袋"
                    onClick={() => setModal({ kind: "cart" })}
                  >
                    <ShoppingBag size={20} />
                    {cart.length > 0 && (
                      <b>{cart.reduce((a, p) => a + p.qty, 0)}</b>
                    )}
                  </button>
                )}
                <div className="profile-wrap">
                  <button
                    className="profile-button"
                    aria-label="个人菜单"
                    onClick={() => setProfileOpen((v) => !v)}
                  >
                    <DefaultAvatar />
                    <ChevronDown size={14} />
                  </button>
                  {profileOpen && (
                    <div className="profile-menu">
                      <strong>你好，用户</strong>
                      <button
                        onClick={() => {
                          setModal({ kind: "audit" });
                          setProfileOpen(false);
                        }}
                      >
                        <ShieldCheck size={16} />
                        操作记录
                      </button>
                      <button
                        onClick={() =>
                          go(seller ? "/buyer/products" : "/seller/home")
                        }
                      >
                        <RefreshCw size={16} />
                        切换至{seller ? "消费者" : "商家"}端
                      </button>
                      <button onClick={() => go("/")}>
                        <LogOut size={16} />
                        返回入口
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </header>
            <main className={`main ${page === "agent" ? "agent-main" : ""}`}>
              {loadError && (
                <div className="api-error" role="alert">
                  {loadError} <button onClick={refresh}>重新连接</button>
                </div>
              )}
              {page === "home" && seller && (
                <DataDashboard analytics={business.analytics} {...core} />
              )}
              {page === "orders" && seller && <SellerOrders {...core} />}
              {page === "products" &&
                (seller ? <SellerProducts {...core} /> : <Catalog {...core} />)}
              {page === "tickets" && seller && <TicketPage {...core} />}
              {page === "agent" && (
                <LiveAgent
                  key={seller ? "seller" : "buyer"}
                  seller={seller}
                  {...core}
                />
              )}
              {page === "account" && !seller && <Account {...core} />}
              {![
                "home",
                "products",
                "orders",
                "tickets",
                "agent",
                "account",
              ].includes(page) && (
                <Empty
                  text="这个页面还不存在"
                  detail="通过顶部导航返回首页。"
                />
              )}
            </main>
            {page !== "agent" && !(seller && page === "products") && (
              <Footer seller={seller} />
            )}
          </>
        )}
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {toast}
        </div>
      )}
      {modal && (
        <Modal
          title={
            modal.kind === "product"
              ? modal.product.name
              : modal.kind === "cart"
                ? "我的购物袋"
                : modal.kind === "audit"
                  ? "操作记录"
                  : modal.kind === "edit"
                    ? modal.product
                      ? "编辑商品"
                      : "新建商品"
                    : "欢迎来到 Onda"
          }
          onClose={() => setModal(null)}
          wide={modal.kind === "audit"}
        >
          {modal.kind === "product" && (
            <div className="product-detail">
              <ProductImage product={modal.product} />
              <div className="detail-body">
                <Badge>{modal.product.brand || modal.product.category}</Badge>
                <h2>{modal.product.name}</h2>
                <p className="muted">{modal.product.desc}</p>
                <strong className="detail-price">
                  {money(modal.product.price)}
                </strong>
                <ul className="product-features">
                  {modal.product.features?.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <div className="product-provenance">
                  {modal.product.sourceUrl && (
                    <>
                      <a
                        href={modal.product.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        查看品牌商品来源 <ExternalLink size={14} />
                      </a>
                      <p>
                        来源报价：US$ {modal.product.sourcePrice} ·{" "}
                        {new Date(
                          modal.product.sourceCapturedAt,
                        ).toLocaleDateString("zh-CN")}
                      </p>
                      <p>规格选项：{modal.product.sourceVariant}</p>
                      <small>{modal.product.priceBasis}</small>
                    </>
                  )}
                  <p>当前库存：{modal.product.stock} 件</p>
                </div>
                <Btn
                  disabled={!modal.product.stock}
                  onClick={() => addCart(modal.product)}
                >
                  <ShoppingBag size={17} />
                  加入购物袋
                </Btn>
              </div>
            </div>
          )}
          {modal.kind === "cart" && (
            <>
              <div className="cart-items">
                {cart.length ? (
                  cart.map((p) => (
                    <div className="cart-item" key={p.id}>
                      <ProductImage product={p} />
                      <div>
                        <strong>{p.name}</strong>
                        <p>
                          {money(p.price)} × {p.qty}
                        </p>
                      </div>
                      <button
                        className="icon-button"
                        aria-label={`移除${p.name}`}
                        onClick={() =>
                          setCart((c) => c.filter((x) => x.id !== p.id))
                        }
                      >
                        <X size={17} />
                      </button>
                    </div>
                  ))
                ) : (
                  <Empty
                    text="购物袋还是空的"
                    detail="去商品页，发现适合你的好物。"
                  />
                )}
              </div>
              {cart.length > 0 && (
                <div className="cart-total">
                  <span>
                    合计{" "}
                    <strong>
                      {money(cart.reduce((a, p) => a + p.price * p.qty, 0))}
                    </strong>
                  </span>
                  <Btn
                    onClick={() => {
                      setModal(null);
                      go("/buyer/agent");
                      setToast("可以向 Onda 咨询商品。");
                    }}
                  >
                    咨询 Onda <ArrowRight size={16} />
                  </Btn>
                </div>
              )}
            </>
          )}
          {modal.kind === "audit" && (
            <div className="audit-list">
              {audit.length ? (
                audit.map((a) => (
                  <div key={a.id}>
                    <ShieldCheck size={21} />
                    <div>
                      <strong>{a.title}</strong>
                      <p>
                        {a.role}确认 · {a.date}
                      </p>
                    </div>
                    <Badge>{a.status || "已完成"}</Badge>
                  </div>
                ))
              ) : (
                <Empty
                  text="暂无已确认操作"
                  detail="高风险操作经人工确认后，会显示在这里。"
                />
              )}
            </div>
          )}
          {modal.kind === "edit" && (
            <ProductForm
              product={modal.product}
              onSave={(values) => saveProduct(modal.product, values)}
            />
          )}
          {modal.kind === "login" && (
            <div className="login-choice">
              <Orb />
              <h2>选择你的 Onda 体验</h2>
              <Btn onClick={() => go("/buyer/products")}>
                <ShoppingBag size={18} />
                我是买家
              </Btn>
              <Btn secondary onClick={() => go("/seller/home")}>
                <BarChart3 size={18} />
                我是商家
              </Btn>
            </div>
          )}
        </Modal>
      )}
      {approval && (
        <ApprovalModal
          data={approval}
          onClose={() => setApproval(null)}
          onConfirm={completeApproval}
        />
      )}
    </>
  );
}

function Landing() {
  return (
    <div className="landing">
      <header className="landing-header">
        <Brand />
        <a
          className="github-link"
          href={githubUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="访问 GitHub 项目"
          title="GitHub"
        >
          <Github size={24} />
        </a>
      </header>
      <div className="landing-copy">
        <p className="eyebrow">
          BETTER CHOICES
          <br />A BRIGHTER EVERYDAY
        </p>
        <h1>让美好生活触手可及</h1>
        <p>在 Onda，遇见更好的选择</p>
      </div>
      <div className="role-cards">
        <a className="role-card buyer-role" href="#/buyer/products">
          <Crop
            source="入口页.png"
            rect={[272, 307, 550, 341]}
            className="role-art"
          />
          <div className="role-content">
            <p className="eyebrow">
              FOR
              <br />
              BUYERS
            </p>
            <h2>我是买家</h2>
            <p>发现好物，享受更美好的生活</p>
            <span className="btn-primary">
              进入买家版 <ArrowRight size={19} />
            </span>
          </div>
        </a>
        <a className="role-card seller-role" href="#/seller/home">
          <Crop
            source="入口页.png"
            rect={[851, 307, 551, 341]}
            className="role-art"
          />
          <div className="role-content">
            <p className="eyebrow">
              FOR
              <br />
              SELLERS
            </p>
            <h2>我是卖家</h2>
            <p>轻松管理店铺，连接更多用户</p>
            <span className="btn-primary">
              进入商家版 <ArrowRight size={19} />
            </span>
          </div>
        </a>
      </div>
      <div className="landing-landscape">
        <Crop source="入口页.png" rect={[0, 650, 1672, 291]} />
      </div>
    </div>
  );
}

function SellerProducts({
  products,
  createProduct,
  globalSearch,
  setModal,
  changeProductStatus,
  setToast,
}) {
  const [tab, setTab] = useState("全部商品"),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState("全部分类"),
    [price, setPrice] = useState("价格区间"),
    [sort, setSort] = useState("更新时间"),
    [selected, setSelected] = useState([]),
    [pageNumber, setPageNumber] = useState(1);
  const filtered = products
    .filter(
      (p) =>
        (tab === "全部商品" || p.status === tab) &&
        (category === "全部分类" || p.category === category) &&
        `${p.name} ${p.id}`
          .toLowerCase()
          .includes((search || globalSearch).toLowerCase()) &&
        (price === "价格区间" ||
          (price === "¥ 0 - 299" && p.price <= 299) ||
          (price === "¥ 300 以上" && p.price >= 300)),
    )
    .sort((a, b) =>
      sort === "价格升序"
        ? a.price - b.price
        : sort === "库存升序"
          ? a.stock - b.stock
          : 0,
    );
  const totalPages = Math.max(1, Math.ceil(filtered.length / 12));
  const activePage = Math.min(pageNumber, totalPages);
  const shown = filtered.slice((activePage - 1) * 12, activePage * 12);
  useEffect(
    () => setPageNumber(1),
    [tab, search, category, price, sort, globalSearch],
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>商品管理</h1>
          <p>管理你的商品信息，轻松上架与维护，让更多用户发现美好生活。</p>
        </div>
        <Btn onClick={() => setModal({ kind: "edit" })}>
          <Plus size={21} />
          新建商品
        </Btn>
      </div>
      <div className="management-tabs">
        {["全部商品", "在售", "下架", "草稿"].map((s) => (
          <button
            className={tab === s ? "active" : ""}
            onClick={() => setTab(s)}
            key={s}
          >
            {s}
            <span>
              {s === "全部商品"
                ? products.length
                : products.filter((p) => p.status === s).length}
            </span>
          </button>
        ))}
      </div>
      <div className="table-filters">
        <div className="field-search">
          <Search size={19} />
          <input
            aria-label="搜索商品"
            placeholder="搜索商品名称、SKU 或关键词…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="商品分类"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {["全部分类", ...categories.slice(1)].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="商品状态"
          value={tab}
          onChange={(e) => setTab(e.target.value)}
        >
          {["全部商品", "在售", "下架", "草稿"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="商品价格区间"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        >
          {["价格区间", "¥ 0 - 299", "¥ 300 以上"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="管理商品排序"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          {["更新时间", "价格升序", "库存升序"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <Btn
          secondary
          onClick={() => {
            setSearch("");
            setCategory("全部分类");
            setPrice("价格区间");
            setTab("全部商品");
            setSort("更新时间");
            setSelected([]);
          }}
        >
          <RefreshCw size={17} />
          重置
        </Btn>
      </div>
      {selected.length > 0 && (
        <div className="selection-note">
          已选择 {selected.length} 件商品{" "}
          <button onClick={() => setSelected([])}>取消选择</button>
          <span>上架与下架操作需逐项确认</span>
        </div>
      )}
      <div className="table-shell card">
        <table className="product-table">
          <thead>
            <tr>
              <th>
                <input
                  aria-label="选择全部商品"
                  type="checkbox"
                  checked={
                    filtered.length > 0 &&
                    filtered.every((p) => selected.includes(p.id))
                  }
                  onChange={(e) =>
                    setSelected(
                      e.target.checked ? filtered.map((p) => p.id) : [],
                    )
                  }
                />
              </th>
              <th>商品信息</th>
              <th>价格</th>
              <th>库存</th>
              <th>商品状态</th>
              <th>更新时间 ↕</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p, i) => (
              <tr key={p.id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择${p.name}`}
                    checked={selected.includes(p.id)}
                    onChange={(e) =>
                      setSelected((s) =>
                        e.target.checked
                          ? [...s, p.id]
                          : s.filter((id) => id !== p.id),
                      )
                    }
                  />
                </td>
                <td>
                  <div className="table-product">
                    <ProductImage product={p} />
                    <div>
                      <strong>{p.name}</strong>
                      <small>
                        SKU: ONDA-{p.id} <i /> {p.category}
                      </small>
                    </div>
                  </div>
                </td>
                <td>{money(p.price)}</td>
                <td>
                  {p.stock}
                  <span className={p.stock === 0 ? "stock-zero" : ""}>
                    {p.stock === 0 ? " · 暂无库存" : ""}
                  </span>
                </td>
                <td>
                  <Badge>{p.status}</Badge>
                </td>
                <td className="muted">
                  {p.updatedAt
                    ? new Date(p.updatedAt).toLocaleDateString("zh-CN")
                    : "—"}
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      onClick={() => setModal({ kind: "edit", product: p })}
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => {
                        createProduct({
                          name: `${p.name}（副本）`,
                          desc: p.desc,
                          price: p.price,
                          stock: p.stock,
                          category: p.category,
                        });
                      }}
                    >
                      复制
                    </button>
                    <button onClick={() => changeProductStatus(p)}>
                      {p.status === "在售" ? "下架" : "上架"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && <Empty />}
      </div>
      <div className="table-footer">
        <span>共 {filtered.length} 件商品</span>
        <Pagination
          page={activePage}
          total={totalPages}
          onChange={setPageNumber}
        />
      </div>
    </>
  );
}

function SellerOrders({
  orders,
  products,
  globalSearch,
  requestApproval,
  orderAction,
  go,
}) {
  const [status, setStatus] = useState("全部"),
    [search, setSearch] = useState(""),
    [current, setCurrent] = useState(null),
    [orderPage, setOrderPage] = useState(1);
  const [tracking, setTracking] = useState(""),
    [shippedAt, setShippedAt] = useState("");
  const order = orders.find((o) => o.id === current);
  const productName = (o) =>
    products.find((p) => p.id === o.productId)?.name || o.productId;
  const filtered = orders.filter(
    (o) =>
      (status === "全部" || o.status === status) &&
      `${o.id} ${productName(o)} ${o.tracking}`
        .toLowerCase()
        .includes((search || globalSearch).trim().toLowerCase()),
  );
  const orderPages = Math.max(1, Math.ceil(filtered.length / 12));
  const activeOrderPage = Math.min(orderPage, orderPages);
  useEffect(() => setOrderPage(1), [status, search, globalSearch]);
  const open = (o) => {
    setCurrent(o.id);
    setTracking(o.tracking === "—" ? "" : o.tracking);
    const now = new Date();
    setShippedAt(
      new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16),
    );
  };
  const [rejectionReason, setRejectionReason] = useState("");
  const reviewRefund = (approved) =>
    requestApproval({
      action: approved ? "approve_refund" : "reject_refund",
      target: order.id,
      version: order.version,
      params: approved ? {} : { reason: rejectionReason },
      onSuccess: () => setCurrent(null),
    });
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>订单管理</h1>
          <p>从下单到售后，每一步清晰掌握。</p>
        </div>
        <span className="order-count">共 {orders.length} 笔订单</span>
      </div>
      <div className="order-summary-grid">
        {[
          ["全部", "全部订单", ShoppingBag],
          ["待发货", "待发货", Package],
          ["运输中", "运输中", Truck],
          ["退款审核中", "待审核退款", ShieldAlert],
        ].map(([key, label, Icon]) => (
          <button
            key={key}
            className={`card order-summary ${status === key ? "selected" : ""}`}
            onClick={() => setStatus(key)}
          >
            <span className="feature-icon">
              <Icon size={23} />
            </span>
            <span>
              {label}
              <strong>
                {key === "全部"
                  ? orders.length
                  : orders.filter((o) => o.status === key).length}
              </strong>
            </span>
          </button>
        ))}
      </div>
      <section className="card merchant-orders">
        <div className="order-toolbar">
          <div className="search-bar">
            <Search size={17} />
            <input
              aria-label="搜索订单"
              placeholder="搜索订单号、商品或物流单号"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            aria-label="订单状态"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {[
              "全部",
              "待发货",
              "运输中",
              "已签收",
              "已取消",
              "退款审核中",
              "退款处理中",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="table-shell">
          <table className="orders-table">
            <thead>
              <tr>
                <th>订单 / 下单日期</th>
                <th>商品</th>
                <th>实付金额</th>
                <th>订单状态</th>
                <th>物流单号</th>
                <th>发货日期</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered
                .slice((activeOrderPage - 1) * 12, activeOrderPage * 12)
                .map((o) => (
                  <tr key={o.id}>
                    <td>
                      <strong>{o.id}</strong>
                      <small>{o.date}</small>
                    </td>
                    <td>{productName(o)}</td>
                    <td className="order-money">{money(o.amount)}</td>
                    <td>
                      <Badge>{o.status}</Badge>
                    </td>
                    <td>{o.tracking}</td>
                    <td>{o.shippedAt}</td>
                    <td>
                      <button className="text-button" onClick={() => open(o)}>
                        查看详情 <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!filtered.length && <Empty text="没有符合条件的订单" />}
        <div className="order-table-footer">
          共 {filtered.length} 条订单
          <Pagination
            page={activeOrderPage}
            total={orderPages}
            onChange={setOrderPage}
          />
        </div>
      </section>
      {order && (
        <Modal title="订单详情" onClose={() => setCurrent(null)}>
          <div className="order-detail-heading">
            <div>
              <h2>{productName(order)}</h2>
              <p>{order.id}</p>
            </div>
            <Badge>{order.status}</Badge>
          </div>
          <dl className="order-facts">
            <dt>实付金额</dt>
            <dd>{money(order.amount)}</dd>
            <dt>下单日期</dt>
            <dd>{order.date}</dd>
            <dt>物流单号</dt>
            <dd>{order.tracking}</dd>
            <dt>发货日期</dt>
            <dd>{order.shippedAt}</dd>
            <dt>当前物流状态</dt>
            <dd>
              {["待发货", "已取消"].includes(order.status)
                ? "尚未发货"
                : order.tracking === "—"
                  ? "暂无物流"
                  : ["退款审核中", "退款处理中"].includes(order.status)
                    ? "已签收"
                    : order.status}
            </dd>
          </dl>
          {order.status === "待发货" && (
            <form
              className="shipping-form"
              onSubmit={(e) => {
                e.preventDefault();
                requestApproval({
                  action: "ship_order",
                  target: order.id,
                  version: order.version,
                  params: { tracking: tracking.trim(), shippedAt },
                  onSuccess: () => setCurrent(null),
                });
              }}
            >
              <h3>发货信息</h3>
              <label>
                物流单号
                <input
                  aria-label="物流单号"
                  value={tracking}
                  onChange={(e) => setTracking(e.target.value)}
                  required
                  pattern={"[A-Za-z0-9\\x2D]{6,40}"}
                  placeholder="填写物流单号"
                />
              </label>
              <label>
                发货日期
                <input
                  aria-label="发货日期"
                  type="datetime-local"
                  value={shippedAt}
                  onChange={(e) => setShippedAt(e.target.value)}
                  required
                />
              </label>
              <div className="modal-actions">
                <Btn
                  secondary
                  type="button"
                  onClick={() => orderAction(order, "cancel")}
                >
                  取消订单
                </Btn>
                <Btn type="submit">
                  <Truck size={17} />
                  登记发货
                </Btn>
              </div>
            </form>
          )}
          {order.status === "退款审核中" && (
            <label className="form-label">
              拒绝原因（拒绝退款时必填）
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={2}
              />
            </label>
          )}
          {order.status === "退款审核中" && (
            <div className="modal-actions">
              <Btn secondary onClick={() => reviewRefund(false)}>
                拒绝退款
              </Btn>
              <Btn onClick={() => reviewRefund(true)}>同意退款</Btn>
            </div>
          )}
          <div className="order-related">
            <button
              className="text-button"
              onClick={() => {
                setCurrent(null);
                go("/seller/tickets");
              }}
            >
              前往工单管理 <ArrowRight size={15} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function TicketPage({
  tickets,
  orders,
  products,
  globalSearch,
  requestApproval,
  setToast,
}) {
  const [tab, setTab] = useState("全部"),
    [type, setType] = useState("全部问题类型"),
    [selected, setSelected] = useState([]),
    [current, setCurrent] = useState(null),
    [note, setNote] = useState("");
  const filtered = tickets.filter(
    (t) =>
      (tab === "全部" || t.status === tab) &&
      (type === "全部问题类型" || t.type === type) &&
      `${t.id} ${t.user} ${t.description} ${t.orderId}`.includes(globalSearch),
  );
  const ticket = current ? tickets.find((t) => t.id === current) : null;
  const order = ticket ? orders.find((o) => o.id === ticket.orderId) : null;
  const finish = () =>
    requestApproval({
      action: "close_ticket",
      target: ticket.id,
      version: ticket.version,
      params: { note: note.trim() || "工单已审核处理。" },
      onSuccess: () => {
        setCurrent(null);
        setNote("");
      },
    });
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>工单管理</h1>
          <p>及时处理用户问题，提供更好的服务体验</p>
        </div>
        <span className="risk-reminder">
          <ShieldCheck size={16} />
          高风险操作需人工确认
        </span>
      </div>
      <section className="ticket-card card">
        <div className="ticket-toolbar">
          <div className="ticket-tabs">
            {["全部", "待处理", "处理中", "已完成"].map((s) => (
              <button
                className={tab === s ? "active" : ""}
                key={s}
                onClick={() => setTab(s)}
              >
                {s}
                <span>
                  {s === "全部"
                    ? tickets.length
                    : tickets.filter((t) => t.status === s).length}
                </span>
              </button>
            ))}
          </div>
          <select
            aria-label="问题类型"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {[
              "全部问题类型",
              "物流配送",
              "商品咨询",
              "售后退款",
              "使用咨询",
              "订单问题",
              "其他问题",
            ].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="table-shell">
          <table className="ticket-table">
            <thead>
              <tr>
                <th>
                  <input
                    aria-label="选择全部工单"
                    type="checkbox"
                    checked={
                      filtered.length > 0 &&
                      filtered.every((t) => selected.includes(t.id))
                    }
                    onChange={(e) =>
                      setSelected(
                        e.target.checked ? filtered.map((t) => t.id) : [],
                      )
                    }
                  />
                </th>
                <th>工单编号</th>
                <th>用户</th>
                <th>问题类型</th>
                <th>问题描述</th>
                <th>状态 / 风险</th>
                <th>创建时间 ↕</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id}>
                  <td>
                    <input
                      aria-label={`选择工单${t.id}`}
                      type="checkbox"
                      checked={selected.includes(t.id)}
                      onChange={(e) =>
                        setSelected((s) =>
                          e.target.checked
                            ? [...s, t.id]
                            : s.filter((id) => id !== t.id),
                        )
                      }
                    />
                  </td>
                  <td>#{t.id}</td>
                  <td>
                    <div className="table-user">
                      <span>
                        <UserRound size={19} />
                      </span>
                      <div>
                        {t.user}
                        <small>{t.phone}</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="type-label">
                      {t.type === "物流配送" ? (
                        <Truck size={18} />
                      ) : t.type === "售后退款" ? (
                        <Package size={18} />
                      ) : (
                        <FileText size={18} />
                      )}{" "}
                      {t.type}
                    </div>
                  </td>
                  <td className="ticket-description" title={t.description}>
                    {t.description}
                  </td>
                  <td>
                    <div className="ticket-badges">
                      <Badge>{t.status}</Badge>
                      {t.risk === "高" && <Badge tone="red">高风险</Badge>}
                    </div>
                  </td>
                  <td className="muted ticket-date">{t.date}</td>
                  <td>
                    <button
                      className="soft-button"
                      onClick={() => {
                        setCurrent(t.id);
                        setNote("");
                      }}
                    >
                      {t.status === "已完成" ? "查看" : "处理"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && <Empty />}
        </div>
        <div className="table-footer">
          <span>
            共 {filtered.length} 条记录
            {selected.length ? ` · 已选择 ${selected.length} 条` : ""}
          </span>
          <div className="pagination">
            <button disabled aria-label="上一页">
              <ChevronLeft size={16} />
            </button>
            <button className="active">1</button>
            <button disabled aria-label="下一页">
              <ChevronRight size={16} />
            </button>
            <span>10 条 / 页</span>
          </div>
        </div>
      </section>
      {ticket && (
        <Modal title="工单详情" onClose={() => setCurrent(null)}>
          <div className="ticket-detail-heading">
            <strong>#{ticket.id}</strong>
            <Badge>{ticket.status}</Badge>
            <Badge
              tone={
                ticket.risk === "高"
                  ? "red"
                  : ticket.risk === "中"
                    ? "amber"
                    : "green"
              }
            >
              {ticket.risk}风险
            </Badge>
          </div>
          <div className="info-grid">
            <div>
              <small>用户</small>
              {ticket.user} · {ticket.phone}
            </div>
            <div>
              <small>问题类型</small>
              {ticket.type}
            </div>
            <div>
              <small>关联订单</small>
              {ticket.orderId}
            </div>
            <div>
              <small>创建时间</small>
              {ticket.date}
            </div>
          </div>
          <div className="quote-box">{ticket.description}</div>
          {order && (
            <div className="logistics-box">
              <h4>
                <Truck size={18} />
                订单与物流
              </h4>
              <dl>
                <dt>商品</dt>
                <dd>{products.find((p) => p.id === order.productId)?.name}</dd>
                <dt>物流单号</dt>
                <dd>{order.tracking}</dd>
                <dt>发货日期</dt>
                <dd>{order.shippedAt}</dd>
                <dt>当前状态</dt>
                <dd>{order.status}</dd>
              </dl>
            </div>
          )}
          {ticket.notes.map((n, i) => (
            <p className="ticket-note" key={i}>
              {n.text}
              <small>{n.date}</small>
            </p>
          ))}
          {ticket.status !== "已完成" && (
            <>
              <label className="form-label">
                处理回复
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="记录处理结果或给用户的回复…"
                  rows={3}
                />
              </label>
              <div className="modal-actions">
                <Btn
                  secondary
                  onClick={() => {
                    requestApproval({
                      action: "update_ticket",
                      target: ticket.id,
                      version: ticket.version,
                      params: {
                        status: "处理中",
                        note: note.trim() || "客服已接手工单。",
                      },
                    });
                  }}
                >
                  设为处理中
                </Btn>
                <Btn onClick={finish}>
                  {ticket.risk === "高" ? (
                    <ShieldAlert size={16} />
                  ) : (
                    <Check size={16} />
                  )}
                  审核并完成
                </Btn>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}

function Account({ orders, products, orderAction, go }) {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>我的订单</h1>
          <p>每一份期待，都有迹可循。</p>
        </div>
      </div>
      <div className="account-banner card">
        <span className="account-avatar">
          <UserRound size={27} />
        </span>
        <div>
          <h3>你好，用户</h3>
          <p>欢迎回到你的美好日常</p>
        </div>
      </div>
      <div className="order-list">
        {orders.map((o) => {
          const p = products.find((x) => x.id === o.productId) || {
            name: o.productName,
            crop: null,
          };
          return (
            <article className="order-card card" key={o.id}>
              <div className="order-top">
                <span>
                  订单号 {o.id} <small>下单日期 {o.date}</small>
                </span>
                <Badge>{o.status}</Badge>
              </div>
              <div className="order-body">
                <ProductImage
                  product={{ ...p, image: p.image || o.productImage }}
                />
                <div>
                  <h3>{p.name}</h3>
                  <p className="muted">数量 1 · {p.desc}</p>
                  <strong>{money(o.amount)}</strong>
                </div>
                <dl>
                  <dt>物流单号</dt>
                  <dd>{o.tracking}</dd>
                  <dt>发货日期</dt>
                  <dd>{o.shippedAt}</dd>
                  <dt>当前物流状态</dt>
                  <dd>{o.fulfillmentStatus || o.status}</dd>
                </dl>
              </div>
              <div className="order-actions">
                {o.status === "待发货" && (
                  <Btn secondary onClick={() => orderAction(o, "cancel")}>
                    取消订单
                  </Btn>
                )}
                {o.status === "已签收" && (
                  <Btn secondary onClick={() => orderAction(o, "refund")}>
                    申请退款
                  </Btn>
                )}
                <button
                  className="text-button"
                  onClick={() => go("/buyer/agent")}
                >
                  咨询订单 <ArrowRight size={15} />
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

function Modal({ title, onClose, children, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    const handler = (e) => {
      if (
        [...document.querySelectorAll('[role="dialog"]')].at(-1) !== ref.current
      )
        return;
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        onClose();
      }
      if (e.key === "Tab") {
        const nodes = ref.current?.querySelectorAll(
          'button:not(:disabled),input,select,textarea,a[href],[tabindex="0"]',
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      setTimeout(() => {
        if (!document.querySelector('[role="dialog"]'))
          document.body.style.overflow = "";
      }, 0);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
        tabIndex={-1}
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="关闭弹窗"
            onClick={onClose}
          >
            <X size={22} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </section>
    </div>
  );
}
function ApprovalModal({ data, onClose, onConfirm }) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal
      title="人工确认"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="approval-symbol">
        <ShieldAlert size={32} />
      </div>
      <div className="approval-title">
        <h2>{data.title}</h2>
        <Badge tone="red">高风险操作</Badge>
      </div>
      <p className="approval-description">{data.description}</p>
      <div className="approval-facts">
        <div>
          <span>操作对象</span>
          <strong>{data.target}</strong>
        </div>
        {data.amount != null && (
          <div>
            <span>涉及金额</span>
            <strong>{money(data.amount)}</strong>
          </div>
        )}
        <div>
          <span>当前状态</span>
          <Badge tone="amber">等待人工确认</Badge>
        </div>
      </div>
      {data.result?.changes && (
        <div className="proposal-changes">
          {Object.entries(data.result.changes).map(([key, change]) => (
            <div key={key}>
              <strong>
                {{
                  status: "状态",
                  price: "价格",
                  stock: "库存",
                  plannedQuantity: "计划补货数量",
                  tracking: "物流单号",
                  shippedAt: "发货日期",
                  name: "商品名称",
                  desc: "商品说明",
                  category: "商品分类",
                  refundStatus: "退款状态",
                  fulfillmentStatus: "物流状态",
                  notes: "处理记录",
                }[key] || key}
              </strong>
              <span>
                {typeof change.before === "object"
                  ? "原记录"
                  : String(change.before ?? "—")}{" "}
                →{" "}
                {typeof change.after === "object"
                  ? JSON.stringify(change.after)
                  : String(change.after)}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="modal-actions">
        <Btn secondary disabled={busy} onClick={onClose}>
          暂不操作
        </Btn>
        <Btn
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onConfirm();
            } finally {
              setBusy(false);
            }
          }}
        >
          <ShieldCheck size={17} />
          确认执行
        </Btn>
      </div>
    </Modal>
  );
}
function ProductForm({ product, onSave }) {
  const [name, setName] = useState(product?.name || ""),
    [price, setPrice] = useState(product?.price || ""),
    [stock, setStock] = useState(product?.stock ?? 0),
    [category, setCategory] = useState(product?.category || "生活电器"),
    [desc, setDesc] = useState(product?.desc || "");
  return (
    <form
      className="product-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!name.trim()) return;
        onSave({
          name: name.trim(),
          price: Number(price),
          stock: Number(stock),
          category,
          desc,
        });
      }}
    >
      <label className="form-label">
        商品名称
        <input
          required
          maxLength={50}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="输入商品名称"
        />
      </label>
      <div className="form-grid">
        <label className="form-label">
          售价（元）
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </label>
        <label className="form-label">
          库存（件）
          <input
            required
            type="number"
            min="0"
            step="1"
            value={stock}
            onChange={(e) => setStock(e.target.value)}
          />
        </label>
      </div>
      <label className="form-label">
        商品分类
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.slice(1).map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </label>
      <label className="form-label">
        一句话介绍
        <textarea
          rows={2}
          maxLength={100}
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
      </label>
      <p className="muted">
        {product
          ? "保存信息不会改变当前在售状态。"
          : "新商品将保存为草稿，确认上架后对消费者可见。"}
      </p>
      <div className="modal-actions">
        <Btn type="submit">
          <Check size={17} />
          保存商品
        </Btn>
      </div>
    </form>
  );
}

const root =
  import.meta.hot?.data.root ?? createRoot(document.getElementById("root"));
if (import.meta.hot) import.meta.hot.data.root = root;
root.render(<App />);
