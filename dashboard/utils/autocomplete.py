"""
[通用工具与组件层] 产品名称联想输入组件
===================================
基于 Streamlit 自定义 HTML 组件实现的下拉联想选择框。

功能：
- 空值聚焦时展示全量产品（拼音首字母 A-Z 排序）
- 输入时实时模糊匹配过滤
- 鼠标点击 / 回车选中回填
- ESC / 失焦 / 点击外部关闭下拉
- 下拉未展开时回车触发提交表单

技术栈：
- 拼音排序：pinyin-pro（CDN 加载，无需 pip install）
- 数据传输：postMessage → Streamlit.setComponentValue

职责边界：
- 仅负责 UI 交互，不包含业务逻辑
- 产品数据由调用方传入
"""

import json
import streamlit.components.v1 as components

# ============================================
# 模拟产品数据
# TODO: 替换为后端 API 调用，获取全量产品列表
# 替换方式：将 MOCK_PRODUCTS 改为从后端接口获取，例如：
#   import requests
#   response = requests.get("http://your-api/products")
#   MOCK_PRODUCTS = response.json()
# ============================================
MOCK_PRODUCTS = [
    "红富士苹果", "进口香蕉", "赣南脐橙", "巨峰葡萄", "麒麟西瓜",
    "丹东草莓", "智利蓝莓", "海南芒果", "香水菠萝", "福建蜜柚",
    "红心火龙果", "徐香猕猴桃", "智利车厘子", "阳山水蜜桃", "新疆哈密瓜",
    "烟台红富士", "都乐香蕉", "褚橙", "阳光玫瑰葡萄", "特小凤西瓜",
    "章姬草莓", "秘鲁蓝莓", "台农芒果", "金钻凤梨", "文旦柚",
    "越南火龙果", "翠香猕猴桃", "美国车厘子", "奉化水蜜桃", "西州蜜瓜",
    "蒙自石榴", "百香果", "牛油果", "猫山王榴莲", "椰青",
    "妃子笑荔枝", "龙眼", "山竹", "释迦果", "莲雾",
    "冰糖心苹果", "黄金奇异果", "伦晚脐橙", "夏黑葡萄", "早春红玉西瓜",
    "红颜草莓", "怡颗莓蓝莓", "凯特芒果", "都乐金菠萝", "三红蜜柚",
    "燕窝果", "红心猕猴桃", "拉宾斯车厘子", "龙泉驿水蜜桃", "伽师哈密瓜",
]


def autocomplete_input(
    products: list[str] | None = None,
    value: str = "",
    key: str = "autocomplete",
    placeholder: str = "输入产品名称搜索...",
    height: int = 320,
) -> str | None:
    """
    渲染带下拉联想的产品名称输入框。

    参数：
        products: 产品名称列表，None 则使用默认模拟数据
        value:  当前已选值（用于回填显示）
        key:    组件唯一标识
        placeholder: 输入框占位文字
        height: 组件高度（px），需容纳输入框 + 下拉面板（最大 280px）

    返回：
        - 选中产品时：返回产品名称字符串
        - 按回车提交时：返回 JSON 字符串 '{"action":"submit","value":"..."}'
        - 未操作时：返回 None
    """
    if products is None:
        products = MOCK_PRODUCTS

    products_json = json.dumps(products, ensure_ascii=False)
    # 对 value 做 JSON 转义，防止 XSS
    safe_value = json.dumps(value if isinstance(value, str) else "", ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://unpkg.com/pinyin-pro@3/dist/index.js">
</script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
    font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont,
                 "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: transparent;
    padding: 0;
    margin: 0;
}}

.autocomplete-wrapper {{
    position: relative;
    width: 100%;
}}

/* ----- 输入框 ----- */
.ac-input {{
    width: 100%;
    height: 38px;
    padding: 6px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.5;
    color: #262730;
    background: #fff;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}}
.ac-input:focus {{
    border-color: #f97316;
    box-shadow: 0 0 0 1px rgba(249,115,22,0.25);
}}
.ac-input::placeholder {{
    color: #9ca3af;
}}

/* ----- 下拉面板 ----- */
.ac-dropdown {{
    display: none;
    position: absolute;
    top: 42px;
    left: 0;
    right: 0;
    max-height: 280px;
    overflow-y: auto;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 6px 16px rgba(0,0,0,0.10);
    z-index: 9999;
}}
.ac-dropdown.show {{
    display: block;
}}

/* ----- 下拉选项 ----- */
.ac-item {{
    padding: 8px 12px;
    cursor: pointer;
    font-size: 14px;
    color: #262730;
    transition: background-color 0.10s;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.ac-item:last-child {{ border-bottom: none; }}
.ac-item:hover {{ background: #fff7ed; }}
.ac-item.active {{
    background: #fff7ed;
    color: #f97316;
}}

/* ----- 空状态提示 ----- */
.ac-empty {{
    padding: 24px 12px;
    text-align: center;
    color: #9ca3af;
    font-size: 13px;
    user-select: none;
}}

/* ----- 滚动条美化 ----- */
.ac-dropdown::-webkit-scrollbar {{ width: 5px; }}
.ac-dropdown::-webkit-scrollbar-track {{ background: transparent; }}
.ac-dropdown::-webkit-scrollbar-thumb {{
    background: #d1d5db;
    border-radius: 3px;
}}
</style>
</head>
<body>

<div class="autocomplete-wrapper">
    <input
        type="text"
        class="ac-input"
        id="acInput"
        placeholder="{placeholder}"
        value={safe_value}
        autocomplete="off"
    />
    <div class="ac-dropdown" id="acDropdown"></div>
</div>

<script>
(function () {{
    const products = {products_json};
    const input = document.getElementById('acInput');
    const dropdown = document.getElementById('acDropdown');
    let activeIndex = -1;
    let sortedProducts = [];

    // ========================================
    // 拼音首字母排序
    // ========================================
    function initSorted() {{
        sortedProducts = [...products].sort(function (a, b) {{
            var pa = window.pinyinPro.pinyin(a, {{
                toneType: 'none',
                type: 'array'
            }})[0][0];
            var pb = window.pinyinPro.pinyin(b, {{
                toneType: 'none',
                type: 'array'
            }})[0][0];
            return pa.localeCompare(pb, 'zh');
        }});
    }}
    // 页面加载时初始化排序
    initSorted();

    // ========================================
    // 渲染下拉列表
    // ========================================
    function renderDropdown(items) {{
        dropdown.innerHTML = '';
        activeIndex = -1;

        if (items.length === 0) {{
            var empty = document.createElement('div');
            empty.className = 'ac-empty';
            empty.textContent = '暂无匹配产品';
            dropdown.appendChild(empty);
        }} else {{
            items.forEach(function (item, idx) {{
                var div = document.createElement('div');
                div.className = 'ac-item';
                div.textContent = item;
                div.addEventListener('mousedown', function (e) {{
                    e.preventDefault(); // 阻止 input 失焦先于 click 触发
                    selectItem(item);
                }});
                dropdown.appendChild(div);
            }});
        }}
    }}

    function updateActive() {{
        var items = dropdown.querySelectorAll('.ac-item');
        items.forEach(function (item, i) {{
            if (i === activeIndex) {{
                item.classList.add('active');
                item.scrollIntoView({{ block: 'nearest' }});
            }} else {{
                item.classList.remove('active');
            }}
        }});
    }}

    function getVisibleItems() {{
        return Array.from(dropdown.querySelectorAll('.ac-item'));
    }}

    // ========================================
    // 显示 / 过滤逻辑
    // ========================================
    function showAll() {{
        renderDropdown(sortedProducts);
        dropdown.classList.add('show');
    }}

    function filterAndShow(keyword) {{
        var lower = keyword.toLowerCase();
        var filtered = sortedProducts.filter(function (p) {{
            return p.toLowerCase().indexOf(lower) !== -1;
        }});
        renderDropdown(filtered);
        dropdown.classList.add('show');
    }}

    function closeDropdown() {{
        dropdown.classList.remove('show');
        activeIndex = -1;
    }}

    // ========================================
    // 选中产品 → 回填 + 传回 Python
    // ========================================
    function selectItem(name) {{
        input.value = name;
        closeDropdown();
        sendToPython(name);
    }}

    // ========================================
    // 向 Streamlit 发送数据
    // 格式遵循 Streamlit 自定义组件的 postMessage 协议
    // ========================================
    function sendToPython(data) {{
        window.parent.postMessage({{
            isStreamlitMessage: true,
            type: 'streamlit:setComponentValue',
            value: data
        }}, '*');
    }}

    // ========================================
    // 事件监听
    // ========================================

    // 获得焦点 → 空值时展示全量产品
    input.addEventListener('focus', function () {{
        if (input.value.trim() === '') {{
            showAll();
        }} else {{
            filterAndShow(input.value.trim());
        }}
    }});

    // 输入文字 → 实时过滤
    input.addEventListener('input', function () {{
        var val = input.value.trim();
        if (val === '') {{
            showAll();
        }} else {{
            filterAndShow(val);
        }}
    }});

    // 键盘交互
    input.addEventListener('keydown', function (e) {{
        var items = getVisibleItems();
        var isOpen = dropdown.classList.contains('show');

        if (e.key === 'ArrowDown') {{
            e.preventDefault();
            if (items.length > 0) {{
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                updateActive();
            }}
        }} else if (e.key === 'ArrowUp') {{
            e.preventDefault();
            if (items.length > 0) {{
                activeIndex = Math.max(activeIndex - 1, 0);
                updateActive();
            }}
        }} else if (e.key === 'Enter') {{
            if (isOpen && items.length > 0) {{
                // 下拉展开 + 有匹配 → 选中第一项（或键盘高亮项）
                e.preventDefault();
                e.stopPropagation();
                var target = (activeIndex >= 0 && activeIndex < items.length)
                    ? items[activeIndex].textContent
                    : items[0].textContent;
                selectItem(target);
            }} else {{
                // 下拉未展开 / 无匹配 → 发出提交信号
                e.preventDefault();
                e.stopPropagation();
                closeDropdown();
                sendToPython(JSON.stringify({{
                    action: 'submit',
                    value: input.value.trim()
                }}));
            }}
        }} else if (e.key === 'Escape') {{
            closeDropdown();
        }}
    }});

    // 失焦 → 延迟关闭（让 mousedown 事件先触发）+ 把当前值发回 Python
    input.addEventListener('blur', function () {{
        setTimeout(closeDropdown, 150);
        var val = input.value.trim();
        if (val) {{
            sendToPython(val);
        }}
    }});

    // 点击组件外部 → 关闭下拉
    document.addEventListener('click', function (e) {{
        if (!e.target.closest('.autocomplete-wrapper')) {{
            closeDropdown();
        }}
    }});
}})();
</script>
</body>
</html>"""

    return components.html(html, height=height)
