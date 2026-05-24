from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "策略筆記" / "assets"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msjh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msjhbd.ttc")


@dataclass(frozen=True)
class Annotation:
    """
    用途與流程：描述策略示意圖上的單一文字標註、箭頭與對應資料點。
    參數：index 是價格序列中的位置；title 是標註標題；body 是較完整的解釋文字；kind 用來決定顏色語意。
    回傳與錯誤：這是資料容器，不直接回傳值；若 index 超出資料範圍，繪圖函式會在使用時忽略或由 Python 索引錯誤暴露。
    """

    index: int
    title: str
    body: str
    kind: str = "info"


@dataclass(frozen=True)
class StrategyImageSpec:
    """
    用途與流程：保存一張策略筆記圖片的所有可變內容，讓同一個 renderer 可重複產生一致版面。
    參數：filename 是輸出 PNG；title/subtitle 是圖上標題；series 是示意價格；overlays 是額外線條；annotations 是圖中標註；steps 是右側閱讀指引；note 是底部風險提示。
    回傳與錯誤：這是資料容器，不直接回傳值；缺少必要序列資料時由 render_strategy_image 檢查並拋出 ValueError。
    """

    filename: str
    title: str
    subtitle: str
    series: tuple[float, ...]
    overlays: tuple[tuple[str, tuple[float, ...], str], ...]
    annotations: tuple[Annotation, ...]
    steps: tuple[str, ...]
    note: str


def main() -> int:
    """
    用途與流程：產生策略筆記所需的所有教學示意圖，輸出到 docs/策略筆記/assets。
    參數：無。
    回傳與錯誤：成功回傳 0；若字型不存在、輸出目錄不可寫或任一圖設定不合法，會拋出例外。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in build_specs():
        render_strategy_image(spec, OUTPUT_DIR / spec.filename)
    return 0


def build_specs() -> tuple[StrategyImageSpec, ...]:
    """
    用途與流程：集中定義所有策略示意圖的價格走勢、圖內標註、右側流程與底部警語。
    參數：無。
    回傳與錯誤：回傳 StrategyImageSpec tuple；內容若有長度不一致會在 render_strategy_image 中被檢查。
    """
    uptrend = (96, 97, 99, 101, 103, 105, 108, 110, 112, 111, 114, 117, 121, 124)
    mean_revert = (104, 103, 101, 99, 96, 93, 91, 92, 94, 97, 99, 101, 102, 103)
    choppy_up = (96, 98, 97, 100, 102, 101, 104, 107, 106, 109, 112, 111, 115, 118)
    absolute = (90, 91, 93, 95, 97, 100, 103, 106, 109, 112, 116, 119, 123, 126)
    orb = (100, 101, 99, 102, 101, 103, 104, 107, 111, 113, 112, 115, 117, 119)
    basket_a = (100, 101, 103, 105, 108, 112, 116, 120, 123, 126, 129, 132)
    basket_b = (100, 99, 100, 101, 102, 101, 102, 103, 105, 106, 108, 109)
    basket_c = (100, 102, 101, 100, 99, 101, 103, 104, 103, 102, 104, 105)
    dip = (100, 103, 106, 108, 110, 107, 102, 96, 92, 94, 96, 99, 102, 105)

    return (
        StrategyImageSpec(
            filename="sma-crossover-trend-explainer.png",
            title="SMA Crossover：快線站上慢線才允許 long",
            subtitle="讀法：先等 slow SMA 暖機，再用 fast SMA > slow SMA 判斷趨勢是否轉強。",
            series=uptrend,
            overlays=(
                ("Fast SMA 20：短期趨勢", moving_average(uptrend, 3), "#2b8a8a"),
                ("Slow SMA 200：長期基準", moving_average(uptrend, 7), "#8a6f2b"),
            ),
            annotations=(
                Annotation(4, "暖機區", "均線資料不足時保持 flat，不把缺資料誤當訊號。", "neutral"),
                Annotation(7, "進場", "fast SMA 上穿 slow SMA，target_position 改為 1.0。", "entry"),
                Annotation(11, "持有", "只要快線仍高於慢線，就延續 long，不重複開倉。", "hold"),
            ),
            steps=(
                "1. 計算 fast / slow SMA。",
                "2. slow SMA 尚未成形時不交易。",
                "3. fast > slow 才翻成 long。",
                "4. fast <= slow 時回到 flat。",
            ),
            note="教學示意圖，非真實市場資料；此策略容易在盤整區反覆進出。",
        ),
        StrategyImageSpec(
            filename="vwap-reversion-trend-explainer.png",
            title="VWAP Reversion：跌離 VWAP 後等待回歸",
            subtitle="讀法：價格低於 rolling VWAP 太多才進場，回到 VWAP 附近就離場。",
            series=mean_revert,
            overlays=(
                ("Rolling VWAP：平均成交成本", moving_average(mean_revert, 5), "#6f4bb2"),
                ("Entry band：跌深門檻", shift(moving_average(mean_revert, 5), -5), "#c05a4a"),
            ),
            annotations=(
                Annotation(5, "跌深但不追空", "z-score 低於 -entry_z，代表偏離 VWAP 夠遠。", "entry"),
                Annotation(7, "進場區", "只在符合 regime 時接受 long，避免下跌趨勢接刀。", "entry"),
                Annotation(10, "回歸出場", "價格回到 VWAP 附近，訊號回到 flat。", "exit"),
            ),
            steps=(
                "1. 用 close 和 volume 算 rolling VWAP。",
                "2. 用 z-score 衡量偏離幅度。",
                "3. 達 entry_z 才允許 long。",
                "4. 接近 VWAP 時離場。",
            ),
            note="教學示意圖，非真實市場資料；強下跌趨勢中需特別檢查 regime filter。",
        ),
        StrategyImageSpec(
            filename="confluence-score-trend-explainer.png",
            title="Confluence Score：多條件同時偏多才進場",
            subtitle="讀法：趨勢、VWAP、RSI 與量能各自加分；分數達 threshold 才輸出 long。",
            series=choppy_up,
            overlays=(
                ("Slow SMA：趨勢底線", moving_average(choppy_up, 6), "#8a6f2b"),
                ("VWAP proxy：平均成本", moving_average(choppy_up, 4), "#6f4bb2"),
            ),
            annotations=(
                Annotation(3, "分數不足", "單一條件偏多還不進場，避免只靠一個指標追價。", "neutral"),
                Annotation(7, "共振進場", "趨勢、價格位置、VWAP、RSI/量能合計達門檻。", "entry"),
                Annotation(10, "冷卻檢查", "若訊號密集，搭配 signal cooldown 檢查 overlap。", "info"),
            ),
            steps=(
                "1. 每個 component 先獨立判斷。",
                "2. 加總為 confluence score。",
                "3. score >= threshold 才進場。",
                "4. 低於門檻就維持 flat。",
            ),
            note="教學示意圖，非真實市場資料；多條件不等於更好，仍需測 trade count 與 OOS。",
        ),
        StrategyImageSpec(
            filename="absolute-momentum-trend-explainer.png",
            title="Absolute Momentum：自身動能為正且站上長均線",
            subtitle="讀法：只看股票自己是否仍在中長期上升趨勢，不和其他股票排名。",
            series=absolute,
            overlays=(
                ("Trend SMA 200：長期趨勢", moving_average(absolute, 7), "#8a6f2b"),
                ("Momentum reference：回看起點", horizontal(absolute, absolute[2]), "#9aa1a8"),
            ),
            annotations=(
                Annotation(2, "回看起點", "momentum_window 用這裡的收盤價當比較基準。", "neutral"),
                Annotation(7, "雙條件通過", "回看報酬 > 0 且 close > trend SMA，才持有。", "entry"),
                Annotation(11, "持有但需控風險", "可再疊 volatility target 或 drawdown risk-off。", "hold"),
            ),
            steps=(
                "1. 計算 lookback return。",
                "2. 計算長期 trend SMA。",
                "3. 兩者同時通過才 long。",
                "4. 任一條件失效就 flat。",
            ),
            note="教學示意圖，非真實市場資料；長期趨勢策略在急跌時可能反應較慢。",
        ),
        StrategyImageSpec(
            filename="orb-volume-vwap-trend-explainer.png",
            title="ORB + Volume + VWAP：開盤區間突破確認",
            subtitle="讀法：先建立 opening range，再要求 close 突破 OR high、站上 VWAP 且量能通過。",
            series=orb,
            overlays=(
                ("OR High：開盤區間上緣", horizontal(orb, max(orb[:4])), "#c05a4a"),
                ("Session VWAP：當日平均成本", moving_average(orb, 4), "#6f4bb2"),
            ),
            annotations=(
                Annotation(2, "建立 OR", "開盤前幾根只收集 OR high / low，不接受訊號。", "neutral"),
                Annotation(7, "假突破檢查", "突破要同時看 VWAP 與 volume，避免低量越線。", "info"),
                Annotation(8, "有效突破", "close > OR high 且 close > VWAP，量能達門檻才 long。", "entry"),
            ),
            steps=(
                "1. 依 session start 建立 OR。",
                "2. OR 完成前保持 flat。",
                "3. close 突破 OR high 才檢查。",
                "4. VWAP / volume / refinement 都通過才進場。",
            ),
            note="教學示意圖，非真實市場資料；ORB 只能用含時間戳的 intraday CSV。",
        ),
        StrategyImageSpec(
            filename="portfolio-relative-momentum-rotation-explainer.png",
            title="Portfolio Rotation：定期把資金移到相對強勢股",
            subtitle="讀法：同一資金池內比較多檔股票的 lookback return，選 top-N 等權持有。",
            series=basket_a,
            overlays=(
                ("Symbol A：目前最強", basket_a, "#2b8a8a"),
                ("Symbol B：中段", basket_b, "#8a6f2b"),
                ("Symbol C：落後", basket_c, "#9aa1a8"),
            ),
            annotations=(
                Annotation(3, "Rebalance", "每週或每月重算排名，不逐檔和自己 B&H 比。", "info"),
                Annotation(6, "Top-N 入選", "只持有排名前 N 且 min_return 通過的股票。", "entry"),
                Annotation(10, "歸因檢查", "用 symbol / group attribution 檢查是否依賴少數贏家。", "hold"),
            ),
            steps=(
                "1. 對齊多檔股票 timestamp。",
                "2. 每次 rebalance 算 lookback return。",
                "3. 套用 breadth / liquidity / group gate。",
                "4. 入選股票等權，其他為 0。",
            ),
            note="教學示意圖，非真實市場資料；策略需和 equal-weight portfolio benchmark 比較。",
        ),
        StrategyImageSpec(
            filename="volume-filter-explainer.png",
            title="Volume Filter：沒有放量就擋掉 long 訊號",
            subtitle="讀法：底層策略先給 long；成交量未達均量倍數時，wrapper 把 long 改成 flat。",
            series=choppy_up,
            overlays=(
                ("Base signal：底層策略訊號", choppy_up, "#2b8a8a"),
                ("Volume gate：量能門檻", moving_average(choppy_up, 5), "#c05a4a"),
            ),
            annotations=(
                Annotation(5, "Long 但量不足", "volume < volume SMA * multiplier，輸出改為 0。", "exit"),
                Annotation(8, "放量通過", "同樣是 long，只有量能達標才保留。", "entry"),
                Annotation(11, "確認參與度", "這不是新 alpha，只是要求訊號有成交量支持。", "info"),
            ),
            steps=(
                "1. 先取得 base strategy signals。",
                "2. 只檢查 target_position > 0 的訊號。",
                "3. 成交量未達門檻就改 flat。",
                "4. flat/非 long 訊號保持原樣。",
            ),
            note="教學示意圖，非真實市場資料；放量可能是買盤，也可能是賣壓事件。",
        ),
        StrategyImageSpec(
            filename="signal-cooldown-explainer.png",
            title="Signal Cooldown：避免同一段行情重複計算 entry",
            subtitle="讀法：接受一次新 long 後，後續 N 根 bar 的新進場會被封鎖。",
            series=(100, 101, 100, 103, 102, 104, 103, 105, 107, 106, 109, 111, 110, 112),
            overlays=(("Base signal：底層訊號", choppy_up, "#2b8a8a"),),
            annotations=(
                Annotation(3, "接受 entry", "第一次 new long 被保留，並啟動 cooldown window。", "entry"),
                Annotation(5, "封鎖重複 entry", "仍在 cooldown 內的新 long 改成 flat，降低 overlap。", "exit"),
                Annotation(9, "冷卻結束", "cooldown 到期後，新的獨立 entry 才可再次接受。", "info"),
            ),
            steps=(
                "1. 判斷是否從 flat 變成 long。",
                "2. 接受後記錄 cooldown_until。",
                "3. 期間的新 long 改成 0。",
                "4. 既有持倉延續不強制平倉。",
            ),
            note="教學示意圖，非真實市場資料；cooldown 是去重工具，不是停損或風控。",
        ),
        StrategyImageSpec(
            filename="volatility-target-explainer.png",
            title="Volatility Target：高波動時只降曝險",
            subtitle="讀法：底層策略仍判斷方向；overlay 只根據 realized volatility 調整 target size。",
            series=dip,
            overlays=(
                ("Price：價格走勢", dip, "#2b8a8a"),
                ("Vol threshold：高波動區", horizontal(dip, 100), "#c05a4a"),
            ),
            annotations=(
                Annotation(3, "正常曝險", "波動未超標時，scale 維持 max_scale。", "hold"),
                Annotation(7, "波動升高", "近期 close-to-close return 擴大，開始計算縮放。", "info"),
                Annotation(9, "降曝險", "target_position = base_position * scale；不加槓桿。", "exit"),
            ),
            steps=(
                "1. 取得 base target_position。",
                "2. 用 lookback returns 算 realized vol。",
                "3. target vol / realized vol 得到 scale。",
                "4. scale 上限預設 1.0，只降不加。",
            ),
            note="教學示意圖，非真實市場資料；降波動可能同時降低報酬。",
        ),
        StrategyImageSpec(
            filename="drawdown-risk-off-explainer.png",
            title="Drawdown Risk-Off：回撤破門檻後暫停持倉",
            subtitle="讀法：用 proxy equity 追蹤單檔策略狀態；破高點回撤門檻後暫時 flat。",
            series=dip,
            overlays=(
                ("Proxy equity：策略資金曲線", dip, "#2b8a8a"),
                ("High-water mark：歷史高點", cumulative_max(dip), "#8a6f2b"),
            ),
            annotations=(
                Annotation(4, "高點", "記錄 proxy equity 的 high-water mark。", "hold"),
                Annotation(8, "觸發 risk-off", "回撤超過 threshold，非零 target 改為 0。", "exit"),
                Annotation(11, "等待重啟", "risk_off_bars 期滿後才重新允許底層策略。", "info"),
            ),
            steps=(
                "1. 用已調整曝險更新 proxy equity。",
                "2. 持續追蹤 high-water mark。",
                "3. drawdown <= -threshold 時啟動 risk-off。",
                "4. 固定 bar 數內保持 flat。",
            ),
            note="教學示意圖，非真實市場資料；這是事後防護，可能錯過反彈。",
        ),
        StrategyImageSpec(
            filename="relative-momentum-stock-pool-filter-explainer.png",
            title="Relative Momentum Filter：只允許股票池 top-N 持倉",
            subtitle="讀法：底層策略仍逐檔判斷；filter 只讓同日相對動能排名前 N 的股票保留曝險。",
            series=basket_a,
            overlays=(
                ("Rank 1：允許持倉", basket_a, "#2b8a8a"),
                ("Rank 2：視 top-N 決定", basket_b, "#8a6f2b"),
                ("Rank 3：落後者", basket_c, "#9aa1a8"),
            ),
            annotations=(
                Annotation(4, "同日排名", "每個 timestamp 橫向比較股票池 lookback return。", "info"),
                Annotation(7, "Top-N allowlist", "入榜股票才保留底層策略的 long。", "entry"),
                Annotation(10, "落榜壓成 flat", "不在 allowlist 的非零曝險改為 0。", "exit"),
            ),
            steps=(
                "1. 先對齊多檔股票日期。",
                "2. 每天計算各股票 lookback return。",
                "3. 選 top-N 且 min_return 通過者。",
                "4. 不在名單內就壓成 flat。",
            ),
            note="教學示意圖，非真實市場資料；這不是完整 portfolio allocation。",
        ),
        StrategyImageSpec(
            filename="portfolio-rotation-group-gates-explainer.png",
            title="Portfolio Group Gates：先檢查群組，再讓候選入選",
            subtitle="讀法：候選股票不只看自己強，還要看所屬 group 是否夠廣、夠強、未過度集中。",
            series=basket_a,
            overlays=(
                ("Semiconductor：群組 A", basket_a, "#2b8a8a"),
                ("Electronics：群組 B", basket_b, "#8a6f2b"),
                ("Financial：群組 C", basket_c, "#9aa1a8"),
            ),
            annotations=(
                Annotation(3, "群組映射", "先用 --symbol-group 定義每檔股票所屬 group。", "info"),
                Annotation(6, "breadth / regime 通過", "同群組正動能比例與等權報酬都達標才放行。", "entry"),
                Annotation(10, "集中度防線", "group cap / contribution gate 避免單一 group 主導。", "exit"),
            ),
            steps=(
                "1. 每檔股票先映射到 group。",
                "2. group breadth 檢查內部正動能比例。",
                "3. group regime 檢查群組等權報酬。",
                "4. group cap / contribution 控制集中度。",
            ),
            note="教學示意圖，非真實市場資料；group mapping 本身就是研究假設。",
        ),
    )


def render_strategy_image(spec: StrategyImageSpec, output_path: Path) -> None:
    """
    用途與流程：把 StrategyImageSpec 繪製成固定尺寸 PNG，包含左側走勢、圖內標註、右側閱讀步驟與底部警語。
    參數：spec 是圖片設定；output_path 是輸出 PNG 路徑。
    回傳與錯誤：回傳 None；若 series 為空或 overlay 長度不符，拋出 ValueError。
    """
    if not spec.series:
        raise ValueError("series must not be empty")
    for _label, values, _color in spec.overlays:
        if len(values) != len(spec.series):
            raise ValueError(f"overlay length mismatch for {spec.filename}")

    width, height = 1800, 1120
    image = Image.new("RGB", (width, height), "#f7f3ea")
    draw = ImageDraw.Draw(image)
    fonts = load_fonts()

    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=36, fill="#fffdf7", outline="#d7cfbf", width=3)
    draw.text((80, 70), spec.title, font=fonts["title"], fill="#1f2933")
    draw_wrapped_text(draw, spec.subtitle, (82, 126), 1120, fonts["subtitle"], "#4b5563", line_gap=8)

    chart = (90, 205, 1235, 800)
    panel = (1290, 180, 1718, 812)
    draw_chart_area(draw, chart, fonts)
    points = map_points(spec.series, chart)

    for label, values, color in spec.overlays:
        overlay_points = map_points(values, chart, min(spec.series), max(spec.series))
        draw.line(overlay_points, fill=color, width=5)
        draw_legend_item(draw, label, color, chart[0] + 18, chart[3] + 28 + 34 * list(spec.overlays).index((label, values, color)), fonts["small"])

    draw.line(points, fill="#1f6f78", width=7, joint="curve")
    for point in points:
        draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill="#1f6f78")

    for annotation in spec.annotations:
        draw_annotation(draw, annotation, points, chart, fonts)

    draw_side_panel(draw, panel, spec.steps, fonts)

    note_box = (80, 930, width - 80, 1040)
    draw.rounded_rectangle(note_box, radius=22, fill="#f3efe4", outline="#d7cfbf", width=2)
    draw.text((note_box[0] + 24, note_box[1] + 18), "讀圖提醒", font=fonts["label"], fill="#7a4b14")
    draw_wrapped_text(draw, spec.note, (note_box[0] + 24, note_box[1] + 56), note_box[2] - note_box[0] - 48, fonts["body"], "#4b5563", line_gap=7)

    image.save(output_path)


def load_fonts() -> dict[str, ImageFont.FreeTypeFont]:
    """
    用途與流程：載入 Microsoft JhengHei 字型，確保中文標註能穩定顯示。
    參數：無。
    回傳與錯誤：回傳字型名稱到 FreeTypeFont 的 dict；字型檔不存在時拋出 FileNotFoundError。
    """
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise FileNotFoundError("Microsoft JhengHei fonts are required")
    return {
        "title": ImageFont.truetype(str(FONT_BOLD), 38),
        "subtitle": ImageFont.truetype(str(FONT_REGULAR), 23),
        "label": ImageFont.truetype(str(FONT_BOLD), 25),
        "body": ImageFont.truetype(str(FONT_REGULAR), 22),
        "small": ImageFont.truetype(str(FONT_REGULAR), 19),
        "tiny": ImageFont.truetype(str(FONT_REGULAR), 17),
    }


def moving_average(values: Iterable[float], window: int) -> tuple[float, ...]:
    """
    用途與流程：產生示意用移動平均線，序列前段不足 window 時改用既有資料平均，避免圖線缺口。
    參數：values 是價格序列；window 是平均視窗。
    回傳與錯誤：回傳與輸入等長的 tuple；window 非正數時拋出 ValueError。
    """
    if window <= 0:
        raise ValueError("window must be positive")
    source = tuple(values)
    output: list[float] = []
    for index in range(len(source)):
        start = max(0, index - window + 1)
        sample = source[start : index + 1]
        output.append(sum(sample) / len(sample))
    return tuple(output)


def shift(values: Iterable[float], amount: float) -> tuple[float, ...]:
    """
    用途與流程：將示意線整體上下平移，用來畫 entry band 或風控門檻。
    參數：values 是原始序列；amount 是加到每個值上的平移量。
    回傳與錯誤：回傳平移後 tuple；此函式不主動拋錯。
    """
    return tuple(value + amount for value in values)


def horizontal(reference: Iterable[float], value: float) -> tuple[float, ...]:
    """
    用途與流程：產生與參考序列等長的水平線。
    參數：reference 用於取得長度；value 是水平線數值。
    回傳與錯誤：回傳 tuple；此函式不主動拋錯。
    """
    return tuple(value for _ in reference)


def cumulative_max(values: Iterable[float]) -> tuple[float, ...]:
    """
    用途與流程：產生示意用 high-water mark 線，讓 drawdown risk-off 圖能對照目前 equity 與歷史高點。
    參數：values 是 proxy equity 或價格示意序列。
    回傳與錯誤：回傳累積最大值 tuple；輸入為空時回傳空 tuple。
    """
    current: float | None = None
    output: list[float] = []
    for value in values:
        current = value if current is None else max(current, value)
        output.append(current)
    return tuple(output)


def draw_chart_area(draw: ImageDraw.ImageDraw, chart: tuple[int, int, int, int], fonts: dict[str, ImageFont.FreeTypeFont]) -> None:
    """
    用途與流程：繪製圖表背景、格線與座標提示，讓每張策略圖有一致的閱讀基準。
    參數：draw 是 PIL ImageDraw；chart 是圖表區域；fonts 是已載入字型。
    回傳與錯誤：回傳 None；座標不合法時由 PIL 繪圖行為暴露。
    """
    x1, y1, x2, y2 = chart
    draw.rounded_rectangle(chart, radius=24, fill="#fbfaf5", outline="#d7cfbf", width=2)
    for i in range(1, 5):
        y = y1 + (y2 - y1) * i / 5
        draw.line((x1 + 16, y, x2 - 16, y), fill="#e8dfcf", width=1)
    for i in range(1, 6):
        x = x1 + (x2 - x1) * i / 6
        draw.line((x, y1 + 16, x, y2 - 16), fill="#eee7dc", width=1)
    draw.text((x1 + 20, y1 + 18), "示意價格 / 曝險狀態", font=fonts["small"], fill="#6b7280")
    draw.text((x2 - 150, y2 - 34), "時間往右", font=fonts["small"], fill="#6b7280")


def map_points(values: tuple[float, ...], chart: tuple[int, int, int, int], min_value: float | None = None, max_value: float | None = None) -> list[tuple[int, int]]:
    """
    用途與流程：把數值序列映射到圖表座標。
    參數：values 是數值序列；chart 是圖表邊界；min_value/max_value 可固定映射尺度。
    回傳與錯誤：回傳座標 list；values 空白時拋出 ValueError。
    """
    if not values:
        raise ValueError("values must not be empty")
    x1, y1, x2, y2 = chart
    low = min(values) if min_value is None else min_value
    high = max(values) if max_value is None else max_value
    if high == low:
        high = low + 1
    pad_x = 60
    pad_y = 65
    output: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        x = x1 + pad_x + round((x2 - x1 - 2 * pad_x) * index / max(1, len(values) - 1))
        y = y2 - pad_y - round((y2 - y1 - 2 * pad_y) * (value - low) / (high - low))
        output.append((x, y))
    return output


def draw_legend_item(draw: ImageDraw.ImageDraw, label: str, color: str, x: int, y: int, font: ImageFont.FreeTypeFont) -> None:
    """
    用途與流程：繪製單一圖例項目。
    參數：draw 是 PIL ImageDraw；label 是圖例文字；color 是線條顏色；x/y 是起點；font 是字型。
    回傳與錯誤：回傳 None；此函式不主動拋錯。
    """
    draw.line((x, y + 10, x + 44, y + 10), fill=color, width=5)
    draw.text((x + 58, y), label, font=font, fill="#4b5563")


def draw_annotation(draw: ImageDraw.ImageDraw, annotation: Annotation, points: list[tuple[int, int]], chart: tuple[int, int, int, int], fonts: dict[str, ImageFont.FreeTypeFont]) -> None:
    """
    用途與流程：在圖表上繪製標註卡片、資料點圓點與連接線。
    參數：annotation 是標註設定；points 是價格序列座標；chart 是圖表邊界；fonts 是已載入字型。
    回傳與錯誤：回傳 None；annotation.index 超出 points 範圍時忽略該標註。
    """
    if annotation.index < 0 or annotation.index >= len(points):
        return
    colors = {
        "entry": ("#e7f4ef", "#1f7a53"),
        "exit": ("#faece7", "#b04632"),
        "hold": ("#eef0fb", "#4353a4"),
        "neutral": ("#f3efe4", "#7a4b14"),
        "info": ("#eaf2f7", "#276178"),
    }
    fill, stroke = colors.get(annotation.kind, colors["info"])
    px, py = points[annotation.index]
    card_width = 310
    card_height = 118
    prefer_right = annotation.index < len(points) / 2
    cx = px + 34 if prefer_right else px - card_width - 34
    cy = py - card_height - 26 if py - chart[1] > 170 else py + 34
    cx = max(chart[0] + 24, min(cx, chart[2] - card_width - 24))
    cy = max(chart[1] + 56, min(cy, chart[3] - card_height - 24))

    draw.line((px, py, cx + card_width / 2, cy + card_height / 2), fill=stroke, width=3)
    draw.ellipse((px - 9, py - 9, px + 9, py + 9), fill=stroke, outline="white", width=3)
    draw.rounded_rectangle((cx, cy, cx + card_width, cy + card_height), radius=18, fill=fill, outline=stroke, width=2)
    draw.text((cx + 16, cy + 12), annotation.title, font=fonts["label"], fill=stroke)
    draw_wrapped_text(draw, annotation.body, (cx + 16, cy + 48), card_width - 32, fonts["tiny"], "#374151", line_gap=4)


def draw_side_panel(draw: ImageDraw.ImageDraw, panel: tuple[int, int, int, int], steps: tuple[str, ...], fonts: dict[str, ImageFont.FreeTypeFont]) -> None:
    """
    用途與流程：繪製右側閱讀流程，讓使用者能依序理解圖中訊號判定。
    參數：draw 是 PIL ImageDraw；panel 是側欄區域；steps 是步驟文字；fonts 是已載入字型。
    回傳與錯誤：回傳 None；此函式不主動拋錯。
    """
    x1, y1, x2, y2 = panel
    draw.rounded_rectangle(panel, radius=24, fill="#f4f7f6", outline="#c9d7d4", width=2)
    draw.text((x1 + 26, y1 + 22), "圖內閱讀順序", font=fonts["label"], fill="#1f4e5f")
    cursor_y = y1 + 72
    for step in steps:
        draw.rounded_rectangle((x1 + 24, cursor_y, x2 - 24, cursor_y + 92), radius=16, fill="#ffffff", outline="#d7e2df", width=1)
        draw_wrapped_text(draw, step, (x1 + 42, cursor_y + 18), x2 - x1 - 86, fonts["body"], "#374151", line_gap=5)
        cursor_y += 106
    draw_wrapped_text(draw, "所有箭頭與價格線皆為策略語意示意；實際績效必須回到回測 artifact 檢查。", (x1 + 28, y2 - 116), x2 - x1 - 56, fonts["small"], "#6b7280", line_gap=5)


def draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, xy: tuple[float, float], max_width: float, font: ImageFont.FreeTypeFont, fill: str, line_gap: int = 6) -> None:
    """
    用途與流程：依像素寬度自動斷行繪製文字，避免圖內中文標註超出框線。
    參數：draw 是 PIL ImageDraw；text 是要繪製的文字；xy 是起點；max_width 是最大寬度；font/fill/line_gap 控制樣式。
    回傳與錯誤：回傳 None；此函式不主動拋錯。
    """
    x, y = xy
    for line in wrap_text(draw, text, max_width, font):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += bbox[3] - bbox[1] + line_gap


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: float, font: ImageFont.FreeTypeFont) -> list[str]:
    """
    用途與流程：以中英文混排安全的方式將文字切成多行，中文可逐字斷行，英文與 CLI token 儘量保留完整。
    參數：draw 是 PIL ImageDraw；text 是原始文字；max_width 是每行最大像素寬；font 是測量字型。
    回傳與錯誤：回傳文字行清單；空字串會回傳單一空行。
    """
    tokens: list[str] = []
    current = ""
    for char in text:
        if char.isspace():
            if current:
                tokens.append(current)
                current = ""
            tokens.append(" ")
        elif ord(char) < 128:
            current += char
        else:
            if current:
                tokens.append(current)
                current = ""
            tokens.append(char)
    if current:
        tokens.append(current)

    lines: list[str] = []
    line = ""
    for token in tokens:
        if token == " ":
            if line and not line.endswith(" "):
                line += " "
            continue
        candidate = line + token
        if not candidate:
            continue
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width or not line:
            line = candidate
            continue
        lines.append(line.rstrip())
        line = token.strip()
    if line:
        lines.append(line.rstrip())
    return lines or [""]


if __name__ == "__main__":
    raise SystemExit(main())
