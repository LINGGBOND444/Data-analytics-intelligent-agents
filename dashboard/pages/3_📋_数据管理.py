"""
[视图层] 数据管理页面
===================
职责：筛选查询 + 分页表格 + 新增/删除 + CSV 导出

架构层级归属：
- 视图层 — 仅负责 UI 渲染与用户交互承接
- 调用 services/data_service.py 执行业务操作
- 所有状态使用 page_data_ 前缀
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import streamlit as st
import pandas as pd

# ---------- 导入服务层 ----------
from services.data_service import (
    query_data,
    insert_data,
    delete_data,
    export_csv,
    get_product_names,
)
from utils.ui_components import confirm_dialog, page_header, empty_state
from utils.common import safe_get, fmt_number


# ============================================
# 页面级状态初始化
# ============================================
if "page_data_filters" not in st.session_state:
    st.session_state["page_data_filters"] = {}
if "page_data_page" not in st.session_state:
    st.session_state["page_data_page"] = 1
if "page_data_confirm_delete" not in st.session_state:
    st.session_state["page_data_confirm_delete"] = None
if "page_data_insert_product" not in st.session_state:
    st.session_state["page_data_insert_product"] = ""


def main() -> None:
    """数据管理页面入口。"""
    page_header("数据管理", "📋")

    # ---------- Tab 切换 ----------
    tab1, tab2, tab3 = st.tabs(["🔍 查询数据", "➕ 新增数据", "📤 导出数据"])

    with tab1:
        _render_query_tab()

    with tab2:
        _render_insert_tab()

    with tab3:
        _render_export_tab()


# ============================================
# Tab 1: 数据查询与展示
# ============================================

def _render_query_tab() -> None:
    """渲染数据查询 Tab。"""
    st.subheader("筛选条件")

    # ---------- 筛选表单 ----------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        date_from = st.date_input(
            "起始日期",
            value=None,
            key="filter_date_from",
            help="留空则不限制起始日期",
        )
    with col2:
        date_to = st.date_input(
            "截止日期",
            value=None,
            key="filter_date_to",
            help="留空则不限制截止日期",
        )
    with col3:
        product_keyword = st.text_input(
            "产品名称（模糊搜索）",
            value="",
            key="filter_product",
            placeholder="输入产品名称关键词...",
        )
    with col4:
        page_size = st.selectbox(
            "每页条数",
            options=[10, 20, 50],
            index=1,
            key="filter_page_size",
        )

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        search_clicked = st.button("🔍 查询", type="primary", use_container_width=True)

    # 构建筛选参数
    filters = {}
    if date_from:
        filters["date_from"] = date_from.strftime("%Y-%m-%d")
    if date_to:
        filters["date_to"] = date_to.strftime("%Y-%m-%d")
    if product_keyword:
        filters["product"] = product_keyword

    st.session_state["page_data_filters"] = filters

    if not search_clicked and not st.session_state.get("page_data_has_searched", False):
        st.info("👆 设置筛选条件后点击「查询」按钮加载数据")
        return

    st.session_state["page_data_has_searched"] = True
    st.divider()

    # ---------- 执行查询 ----------
    success, result = query_data(
        filters,
        page=st.session_state["page_data_page"],
        page_size=page_size,
    )

    if not success:
        st.error(result)
        return

    rows = result["rows"]
    total = result["total"]
    current_page = result["page"]

    # ---------- 分页控件 ----------
    st.caption(f"共 **{total}** 条记录，第 {current_page} / {max(1, (total + page_size - 1) // page_size)} 页")

    total_pages = max(1, (total + page_size - 1) // page_size)
    col_pg1, col_pg2, col_pg3, col_pg4, col_pg5 = st.columns([1, 1, 2, 1, 1])

    with col_pg1:
        if st.button("⬅️ 上一页", disabled=current_page <= 1):
            st.session_state["page_data_page"] = max(1, current_page - 1)
            st.rerun()
    with col_pg2:
        if st.button("➡️ 下一页", disabled=current_page >= total_pages):
            st.session_state["page_data_page"] = min(total_pages, current_page + 1)
            st.rerun()

    # ---------- 数据表格 ----------
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ---------- 删除功能 ----------
        st.divider()
        st.subheader("删除记录")

        delete_id = st.number_input(
            "输入要删除的记录 ID（主键）",
            min_value=1,
            step=1,
            key="delete_id_input",
        )

        if st.button("🗑️ 删除此记录", type="secondary"):
            st.session_state["page_data_confirm_delete"] = delete_id
            st.rerun()

        # 二次确认
        if st.session_state.get("page_data_confirm_delete"):
            confirm_id = st.session_state["page_data_confirm_delete"]
            st.warning(f"⚠️ 确认删除 ID 为 **{confirm_id}** 的记录吗？此操作不可撤销。")

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ 确认删除", type="primary"):
                    success, msg = delete_data(confirm_id)
                    st.session_state["page_data_confirm_delete"] = None
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with col_no:
                if st.button("❌ 取消"):
                    st.session_state["page_data_confirm_delete"] = None
                    st.rerun()
    else:
        empty_state("查询无结果，请调整筛选条件后重试")


# ============================================
# Tab 2: 新增数据
# ============================================

def _render_insert_tab() -> None:
    """渲染新增数据 Tab。"""
    st.subheader("新增业务数据")
    st.caption("填写以下表单，提交后自动写入数据库。")
    st.caption("> 数据将写入 `daily_sales` 表，除产品名称外均为选填。")

    # ============================================
    # 状态桥接 — 在所有 widget 之前应用待处理的修改
    # 原因：Streamlit 不允许在 widget 渲染后修改其 session_state key。
    # 所有需要修改 widget key 的地方（按钮回调、提交成功重置），
    # 都改为设置「待处理状态」page_data_pending_product，
    # 然后在此处（widget 渲染前）统一应用。
    # ============================================
    if "page_data_pending_product" in st.session_state:
        st.session_state["page_data_insert_product"] = st.session_state.pop("page_data_pending_product")

    # 缓存产品名称列表
    if "page_data_insert_products" not in st.session_state:
        st.session_state["page_data_insert_products"] = get_product_names()

    # ---------- 搜索已有产品（展开式快速选择）----------
    products = st.session_state.get("page_data_insert_products", [])
    if products:
        with st.expander("📋 搜索已有产品（可选）", expanded=False):
            search_kw = st.text_input(
                "输入关键词过滤",
                key="ac_search_product",
                placeholder="如输入「苹果」筛选...",
                label_visibility="collapsed",
            )
            matched = [p for p in products if search_kw.lower() in p.lower()] if search_kw else products[:20]
            if matched:
                cols = st.columns(4)
                for i, p in enumerate(matched[:20]):
                    with cols[i % 4]:
                        if st.button(p, key=f"ac_btn_{p}", use_container_width=True):
                            # 通过待处理状态间接修改，避免 widget key 锁定冲突
                            st.session_state["page_data_pending_product"] = p
                            st.rerun()
            else:
                st.caption("无匹配产品，可直接在下方输入框输入新产品名称")

    # ---------- 产品名称文本输入 ----------
    current_product = st.text_input(
        "产品名称 *",
        key="page_data_insert_product",
        placeholder="输入产品名称，或展开上方「搜索已有产品」快速选择",
    )

    # 当前已选产品提示
    if current_product:
        st.info(f"📦 当前产品：**{current_product}**")
    else:
        st.warning("⚠️ 请输入或选择产品名称")

    # ============================================
    # 其余表单字段（不使用 st.form，用普通控件 + 按钮）
    # ============================================
    st.divider()

    # ---------- 自动计算回调 ----------
    def _on_volume_change():
        """销售量变化 → 自动计算销售额 + 库存"""
        v = st.session_state.get("ins_volume", 0.0) or 0.0
        p = st.session_state.get("ins_price", 0.0) or 0.0
        r = st.session_state.get("ins_restock", 0.0) or 0.0
        if v > 0 and p > 0:
            st.session_state["ins_amount"] = round(v * p, 2)
        st.session_state["ins_stock"] = max(0.0, r - v)

    def _on_price_change():
        """单价变化 → 自动计算销售额"""
        v = st.session_state.get("ins_volume", 0.0) or 0.0
        p = st.session_state.get("ins_price", 0.0) or 0.0
        if v > 0 and p > 0:
            st.session_state["ins_amount"] = round(v * p, 2)

    def _on_restock_change():
        """日进货量变化 → 自动计算库存"""
        v = st.session_state.get("ins_volume", 0.0) or 0.0
        r = st.session_state.get("ins_restock", 0.0) or 0.0
        st.session_state["ins_stock"] = max(0.0, r - v)

    col1, col2 = st.columns(2)
    with col1:
        record_date = st.date_input("日期", key="ins_date")
    with col2:
        volume = st.number_input("销售量", min_value=0.0, step=1.0, key="ins_volume", on_change=_on_volume_change)

    col3, col4, col5 = st.columns(3)
    with col3:
        amount = st.number_input("销售额", min_value=0.0, step=0.01, key="ins_amount", help="自动计算：销售量 × 单价")
    with col4:
        price = st.number_input("单价", min_value=0.0, step=0.01, key="ins_price", on_change=_on_price_change)
    with col5:
        restock = st.number_input("日进货量", min_value=0.0, step=1.0, key="ins_restock", on_change=_on_restock_change)

    stock = st.number_input("库存", min_value=0.0, step=1.0, key="ins_stock", help="自动计算：日进货量 − 销售量")

    # ============================================
    # 提交按钮 & 提交逻辑
    # ============================================
    if st.button("✅ 提交新增", type="primary", use_container_width=True):
        if not current_product:
            st.error("产品名称为必填项，请输入或选择产品名称")
        else:
            record = {
                "date": record_date.strftime("%Y-%m-%d"),
                "product": current_product,
                "volume": volume,
                "amount": amount,
                "price": price,
                "restock": restock,
                "stock": stock,
            }
            success, msg = insert_data(record)
            if success:
                # 通过待处理状态重置产品名（而非直接改 widget key）
                st.session_state["page_data_pending_product"] = ""
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ============================================
# Tab 3: CSV 导出
# ============================================

def _render_export_tab() -> None:
    """渲染 CSV 导出 Tab。"""
    st.subheader("导出数据为 CSV")

    filters = st.session_state.get("page_data_filters", {})
    if not filters:
        st.info("请先在「🔍 查询数据」Tab 中设置筛选条件，再回到此处导出")

    st.write("当前筛选条件：")
    st.json(filters if filters else {"（无筛选）": "将导出全部数据"})

    if st.button("📥 导出 CSV", type="primary"):
        success, result = export_csv(filters)
        if success:
            import base64
            b64 = base64.b64encode(result).decode()
            st.download_button(
                label="💾 点击下载 CSV 文件",
                data=result,
                file_name="数据导出.csv",
                mime="text/csv",
            )
        else:
            st.error(result)


if __name__ == "__main__":
    main()
else:
    main()
