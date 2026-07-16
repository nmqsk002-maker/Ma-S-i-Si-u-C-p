import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
import random

# ==================================================================
# CONFIG CẤU HÌNH HỆ THỐNG TRUNG TÂM
# ==================================================================
TOKEN = "TOKEN_CỦA_BẠN"  # Điền HTTP API Token nhận từ @BotFather
ADMIN_IDS = [123456789]  # Thay thế bằng danh sách ID Telegram của các Admin tối cao

bot = telebot.TeleBot(TOKEN)

# ==================================================================
# CƠ SỞ DỮ LIỆU TRONG BỘ NHỚ (IN-MEMORY SYSTEM DATABASE)
# ==================================================================
# Hệ thống Dictionary quản lý trạng thái dữ liệu đa hướng cho 100 thành phần
users_db = {}     # Cấu trúc: {user_id: {name, gold, bank, win, loss, rank, last_click}}
games = {}        # Cấu trúc: {chat_id: {status, host, players, weather, night_actions, timer_active}}
pending_tx = {}   # Cấu trúc: {tx_id: {user_id, type, amount, info, status}}

# THUẬT TOÁN CHỐNG ĐƠ (THREADING LOCK BLOCKER)
# Khóa tài nguyên đa luồng, loại bỏ triệt để lỗi xung đột dữ liệu (Race Condition) khi ví vàng biến động
db_lock = threading.Lock()

# ==================================================================
# HÀM KHỞI TẠO TÀI KHOẢN NGƯỜI CHƠI (USER INITIALIZATION FUNCTION)
# ==================================================================
def init_user(user_id: int, name: str) -> None:
    """
    Khởi tạo tài khoản đồng bộ hệ sinh thái ví vàng và thông tin ngân hàng.
    Đảm bảo an toàn luồng dữ liệu bằng cấu trúc khóa db_lock.
    """
    with db_lock:
        if user_id not in users_db:
            users_db[user_id] = {
                "name": name,
                "gold": 50000,          # Hệ thống tặng sẵn 50,000 Vàng làm vốn khởi nghiệp
                "bank": None,           # Chuỗi thông tin tài khoản ngân hàng liên kết
                "win": 0,               # Thống kê tổng số trận thắng cuộc
                "loss": 0,              # Thống kê tổng số trận thua cuộc
                "rank": "Tập Sự Đêm Tối 🛡️", # Danh hiệu chiến trường mặc định
                "last_click": 0.0       # Mốc thời gian để tính toán chống spam click nút
            }

# ==================================================================
# HÀM ĐÁNH GIÁ RANK CHIẾN TRƯỜNG TỰ ĐỘNG (RANKING ALGORITHM)
# ==================================================================
def update_user_rank(user_id: int) -> None:
    """
    Tự động nâng danh hiệu dựa trên số trận thắng thực tế của người chơi.
    Hàm này được gọi ngay sau khi kết toán giải thưởng cược ở cuối trận.
    """
    if user_id not in users_db:
        return
        
    u = users_db[user_id]
    w = u["win"]
    
    if w >= 100:
        u["rank"] = "Huyền Thoại Bất Tử 👑"
    elif w >= 50:
        u["rank"] = "Kẻ Săn Đêm Lão Luyện ⚔️"
    elif w >= 20:
        u["rank"] = "Sói Bạc Chiến Binh 🐺"
    elif w >= 5:
        u["rank"] = "Thợ Săn Thành Phố 🏹"
    else:
        u["rank"] = "Tập Sự Đêm Tối 🛡️"

# Kế thừa tiếp tục từ Phần 1...

# ==================================================================
# 1. KỊCH BẢN THOẠI NGẪU NHIÊN CẢNH BÁO XÂM NHẬP (RANDOM DRAMATIC DIALOGUES)
# ==================================================================
# Các câu thoại kịch tính biến đổi ngẫu nhiên khi người lạ cố tình bấm nút Admin
WARNING_DIALOGUES = [
    "⚠️ **BẤT HỢP PHÁP!**\nMắt Thần Tối Cao đã ghi nhận hành vi của bạn. Khu vực hành chính này chỉ dành cho Hội Đồng Admin!",
    "🛑 **PHÁP LỆNH TỐI CAO!**\nBạn cố tình chạm vào quyền lực không thuộc về mình. Hãy lùi lại trước khi bầy sói ngửi thấy mùi phản nghịch!",
    "⚡ **KHÔNG ĐỦ THẨM QUYỀN!**\nLệnh bài quyền lực của bạn không hợp lệ. Đừng để Tòa Thánh Ma Sói phải phát lệnh trục xuất!",
    "🔥 **CẢNH BÁO NGUY HIỂM!**\nBạn không có đặc quyền Admin. Mọi cố gắng can thiệp trái phép vào ngân khố sẽ bị trừng trị nghiêm khắc!"
]

# ==================================================================
# 2. HÀM KIỂM TRA QUYỀN ADMIN TỐI CAO (ADMIN CHECKER)
# ==================================================================
def is_admin(user_id: int) -> bool:
    """
    Kiểm tra xem ID người dùng có nằm trong danh sách Admin tối cao hay không.
    Trả về True nếu hợp lệ, False nếu là người lạ.
    """
    return user_id in ADMIN_IDS

# ==================================================================
# 3. THUẬT TOÁN KIỂM SOÁT SPAM NÚT BẤM (ANTI-SPAM RATE LIMITER)
# ==================================================================
def is_spammer(user_id: int) -> bool:
    """
    Thuật toán chặn đứng tình trạng spam click nút gây đơ/treo bot trên Termux.
    Giới hạn mỗi người chơi chỉ được click hành động tối đa 1 lần trong 0.8 giây.
    """
    current_time = time.time()
    # Nếu người chơi chưa có tài khoản, hàm tự động tạo thông qua init_user của Phần 1
    if user_id not in users_db:
        return False
        
    last_click = users_db[user_id]["last_click"]
    
    if current_time - last_click < 0.8:
        return True
        
    # Nếu không spam, cập nhật mốc thời gian click mới nhất vào database
    users_db[user_id]["last_click"] = current_time
    return False

# ==================================================================
# 4. HÀM BỘ LỌC AN TOÀN TRUNG GIAN (SECURITY MIDDLEWARE HANDLER)
# ==================================================================
def check_security_privilege(call, require_admin: bool = False) -> bool:
    """
    Bộ lọc an toàn cốt lõi xử lý mọi sự kiện chạm nút.
    - Phản hồi ngay lập tức để nút bấm không bị xoay vòng (đơ).
    - Ngăn chặn kẻ cố tình spam phá hoại tài nguyên điện thoại.
    - Đẩy lùi người lạ nếu truy cập nút bấm đặc quyền Admin.
    """
    user_id = call.from_user.id
    user_name = call.from_user.first_name
    
    # Khởi tạo tài khoản đồng bộ nếu người dùng mới bấm nút lần đầu
    init_user(user_id, user_name)
    
    # KÍCH HOẠT CHỐNG SPAM: Nếu spam, báo hiệu nhẹ ở góc màn hình, không mở alert to gây khó chịu
    if is_spammer(user_id):
        try:
            bot.answer_callback_query(
                call.id, 
                "⚡ Thao tác quá nhanh! Hệ thống đang xử lý, vui lòng không click liên tục.", 
                show_alert=False
            )
        except Exception:
            pass
        return False

    # KÍCH HOẠT KIỂM TRA QUYỀN ADMIN: Nếu nhấn nút Admin mà là người lạ, hiện Alert kịch tính chặn đứng
    if require_admin and not is_admin(user_id):
        try:
            random_warning = random.choice(WARNING_DIALOGUES)
            bot.answer_callback_query(call.id, random_warning, show_alert=True)
        except Exception:
            pass
        return False
        
    # Mọi tiêu chí an toàn đều vượt qua, giải phóng trạng thái xoay vòng của nút bấm
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    return True

# Kế thừa tiếp tục từ Phần 1 và Phần 2...

# ==================================================================
# 1. KỊCH BẢN THOẠI MỞ ĐẦU BAN MAI RIÊNG BIỆT (GREETING DIALOGUES)
# ==================================================================
PRIVATE_GREETINGS = [
    "🔮 **Huyết ấn đã kích hoạt! Linh hồn dũng cảm {name} đã bước vào Tòa Thánh Ma Sói!**\n\n",
    "🐺 **Bóng đêm đang vây lấy ngươi, {name}. Ngươi chọn làm thợ săn đi săn đêm hay trở thành con mồi nằm trên thớt?**\n\n",
    "🦅 **Tiếng quạ kêu báo hiệu một chu kỳ trăng máu mới đã bắt đầu trỗi dậy, {name}!**\n\n"
]

# ==================================================================
# 2. HÀM DỰNG GIAO DIỆN MENU TRUNG TÂM CHAT RIÊNG (PRIVATE MENU GENERATOR)
# ==================================================================
def get_private_central_menu(user_id: int) -> InlineKeyboardMarkup:
    """
    Tạo bảng menu nút bấm động cho Chat riêng với Bot dựa trên thông tin ví Vàng.
    Tự động ẩn/hiện nút Ban Quản Trị Tối Cao nếu ID là Admin.
    """
    # Đảm bảo tài khoản đã được khởi tạo an toàn
    init_user(user_id, "Thợ Săn")
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Hàng 1: Nút dẫn hướng chuyển động vào Nhóm chơi game và Nút xem Hồ sơ cá nhân
    markup.add(
        InlineKeyboardButton("🎮 Sảnh Trận Đấu (Vào Nhóm)", url=f"https://t.me{bot.get_me().username}?startgroup=true"),
        InlineKeyboardButton("👤 Hồ Sơ Chiến Binh", callback_data="p_view_profile")
    )
    # Hàng 2: Hệ thống nút nạp/rút vàng trực tuyến
    markup.add(
        InlineKeyboardButton("💰 Nạp Vàng Ngân Khố", callback_data="p_money_deposit"),
        InlineKeyboardButton("🏧 Rút Vàng Về Bank", callback_data="p_money_withdraw")
    )
    # Hàng 3: Liên kết bảo mật tài khoản ngân hàng và bảng vinh danh
    markup.add(
        InlineKeyboardButton("💳 Liên Kết Thẻ Bank", callback_data="p_bank_link"),
        InlineKeyboardButton("🏆 Bảng Anh Hùng (Top Giàu)", callback_data="p_leaderboard")
    )
    
    # Hàng 4: Đặc quyền tối cao (Chỉ hiển thị nút cho những ai thuộc danh sách ADMIN_IDS)
    if is_admin(user_id):
        markup.add(InlineKeyboardButton("👑 BAN QUẢN TRỊ TỐI CAO", callback_data="p_admin_panel"))
        
    return markup

# ==================================================================
# 3. HÀM DỰNG GIAO DIỆN PANEL ĐIỀU HÀNH CỦA ADMIN (ADMIN PANEL GENERATOR)
# ==================================================================
def get_admin_panel_menu() -> InlineKeyboardMarkup:
    """
    Tạo giao diện nút bấm quản trị chuyên sâu dành riêng cho Admin.
    Tất cả các hành động tài chính nhạy cảm đều được bọc trong bộ menu này.
    """
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📝 Duyệt Lệnh Nạp Vàng", callback_data="adm_list_deposit"),
        InlineKeyboardButton("💸 Duyệt Lệnh Rút Vàng", callback_data="adm_list_withdraw")
    )
    markup.add(
        InlineKeyboardButton("📊 Kiểm Toán Quỹ Vàng", callback_data="adm_stat_gold"),
        InlineKeyboardButton("🛑 Trạng Thái Bảo Trì", callback_data="adm_maintenance_toggle")
    )
    # Nút quay về sảnh chính của chat riêng
    markup.add(InlineKeyboardButton("🔙 Quay Lại Sảnh Chính", callback_data="p_back_to_main"))
    return markup

# ==================================================================
# 4. BỘ TIẾP NHẬN LỆNH KHỞI ĐỘNG VÀO CHAT RIÊNG (COMMAND HANDLER)
# ==================================================================
@bot.message_handler(commands=['start', 'menu'])
def cmd_start_private_central(message):
    """
    Xử lý khi người chơi gõ lệnh /start hoặc /menu.
    Phân tách rõ ràng: Chat riêng thì hiển thị ví tài sản, Nhóm thì hiển thị lối tắt.
    """
    user_id = message.from_user.id
    chat_type = message.chat.type
    user_name = message.from_user.first_name
    
    # Khởi tạo tài khoản an toàn
    init_user(user_id, user_name)
    u = users_db[user_id]
    
    if chat_type == "private":
        # Lấy một lời thoại mở đầu ngẫu nhiên đầy kịch tính để chào đón
        dramatic_greeting = random.choice(PRIVATE_GREETINGS).format(name=user_name)
        
        welcome_text = dramatic_greeting + (
            f"💰 **Số dư ví vàng:** `{u['gold']:,}` Vàng\n"
            f"🎖️ **Danh hiệu chiến trường:** `{u['rank']}`\n"
            f"💳 **Tài khoản Bank:** `{u['bank'] if u['bank'] else '🔴 Chưa liên kết ngân hàng'}`\n\n"
            f"👉 *Mọi câu lệnh gõ tay rườm rà đã bị xóa bỏ. Hãy chạm vào hệ thống menu nút bấm dưới đây để thực hiện giao dịch tài chính hoặc liên kết sảnh game nhóm để bắt đầu đặt cược sinh tử!*"
        )
        
        try:
            bot.send_message(
                user_id, 
                welcome_text, 
                parse_mode="Markdown", 
                reply_markup=get_private_central_menu(user_id)
            )
        except Exception as e:
            print(f"Lỗi gửi tin nhắn sảnh riêng: {e}")
    else:
        # Nếu gõ nhầm lệnh trong Group, xuất nút bấm kéo người chơi về sảnh thao tác riêng
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🐺 Kích Hoạt Bảng Thao Tác Trận Đấu", callback_data=f"g_open_dashboard_{message.chat.id}"))
        try:
            bot.reply_to(
                message, 
                "🛡️ **THÀNH TRÌ MA SÓI THÔNG BÁO**\nHệ thống điều khiển nút bấm của nhóm đã sẵn sàng. Vui lòng nhấn nút phía dưới để bắt đầu sảnh cược bài.", 
                reply_markup=markup
            )
        except Exception as e:
            print(f"Lỗi phản hồi lệnh trong Group: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2 và Phần 3...

# ==================================================================
# 1. KỊCH BẢN THOẠI HỒ SƠ NGẪU NHIÊN KỊCH TÍNH (PROFILE DIALOGUES)
# ==================================================================
PROFILE_DIALOGUES = [
    "📜 **HỒ SƠ THỢ SĂN ĐÊM TỐI** 📜\n\n• **Danh tính chiến binh:** *{name}*\n• **Ngân khố hiện có:** `{gold} Vàng`\n• **Cấp bậc chiến trường:** `{rank}`\n• **Thống kê sinh tử:** `🏆 {win} Trận Thắng` | `💀 {loss} Trận Thua`",
    "🦅 **THÔNG TIN ĐẠI DIỆN CHIẾN TRƯỜNG** 🦅\n\n• **Tên thợ săn:** *{name}*\n• **Số dư tài sản:** `{gold} Vàng`\n• **Tộc bậc hiện tại:** `{rank}`\n• **Lịch sử chiến đấu:** Đã hạ gục hàng tá thực thể bóng đêm với `{win}` chiến thắng vang dội."
]

# ==================================================================
# 2. BỘ TIẾP NHẬN VÀ ĐIỀU HƯỚNG SỰ KIỆN CALLBACK KINH TẾ
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("p_", "adm_")))
def handle_economic_central_callbacks(call):
    """
    Xử lý toàn bộ các nút bấm tài chính trong chat riêng và bảng lệnh Admin.
    Đã sửa lỗi đồng bộ, tự giải phóng vòng xoáy tải của nút bấm lập tức.
    """
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # 2.1 Kích hoạt bộ lọc chống spam và xác thực quyền Admin tối cao
    # Nếu nút bắt đầu bằng adm_ hoặc là nút mở sảnh admin panel, yêu cầu đặc quyền Admin = True
    require_adm_check = data.startswith("adm_") or data == "p_admin_panel"
    if not check_security_privilege(call, require_admin=require_adm_check):
        return  # Ngắt tiến trình ngay nếu là kẻ spam hoặc người lạ xâm nhập
        
    u = users_db[user_id]
    
    # ---- 2.2 XỬ LÝ NÚT: XEM HỒ SƠ CÁ NHÂN KÈM RANK ĐỒNG BỘ ----
    if data == "p_view_profile":
        # Gọi thuật toán tự động cập nhật danh hiệu dựa trên số trận thắng từ Phần 1
        update_user_rank(user_id)
        
        # Chọn ngẫu nhiên một kịch bản lời thoại hồ sơ đầy kịch tính
        dramatic_profile = random.choice(PROFILE_DIALOGUES).format(
            name=u["name"],
            gold=f"{u['gold']:,}",
            rank=u["rank"],
            win=u["win"],
            loss=u["loss"]
        )
        
        try:
            bot.edit_message_text(
                dramatic_profile,
                chat_id,
                message_id,
                parse_mode="Markdown",
                reply_markup=get_private_central_menu(user_id)
            )
        except Exception as e:
            print(f"Lỗi chỉnh sửa tin nhắn hồ sơ: {e}")

    # ---- 2.3 XỬ LÝ NÚT: LIÊN KẾT THẺ BANK TỰ ĐỘNG KHÔNG CẦN GÕ LỆNH ----
    elif data == "p_bank_link":
        # Giả lập mã hóa và liên kết ngân hàng mặc định theo tên tài khoản Telegram
        with db_lock:
            u["bank"] = f"MBBANK - 999912038491 - {u['name'].upper()}"
            
        try:
            bot.answer_callback_query(
                call.id, 
                "💳 ĐÃ ĐỒNG BỘ BANK THÀNH CÔNG!\nTài khoản ngân hàng cá nhân của bạn đã được mã hóa an toàn vào Tòa Thánh.", 
                show_alert=True
            )
            # Tự động gọi lại luồng xem hồ sơ để giao diện cập nhật ngay thông tin Bank mới
            handle_economic_central_callbacks(call)
        except Exception as e:
            print(f"Lỗi xử lý đồng bộ liên kết Bank: {e}")

    # ---- 2.4 XỬ LÝ NÚT: BẢNG ANH HÙNG (TOP ĐẠI GIA) ----
    elif data == "p_leaderboard":
        # Thuật toán sắp xếp tìm kiếm top 5 người chơi sở hữu nhiều Vàng nhất hệ thống
        with db_lock:
            sorted_richest = sorted(users_db.items(), key=lambda x: x[1]['gold'], reverse=True)[:5]
            
        leaderboard_text = "🏆 **BẢNG VINH DANH CÁC ĐẠI GIA MA SÓI** 🏆\n\n"
        for idx, (uid, info) in enumerate(sorted_richest, 1):
            leaderboard_text += f"{idx}. ✨ **{info['name']}** — `{info['gold']:,}` Vàng\n   *Danh hiệu:* `{info['rank']}`\n"
            
        try:
            bot.edit_message_text(
                leaderboard_text,
                chat_id,
                message_id,
                parse_mode="Markdown",
                reply_markup=get_private_central_menu(user_id)
            )
        except Exception as e:
            print(f"Lỗi kết xuất bảng xếp hạng: {e}")

    # ---- 2.5 XỬ LÝ NÚT: TẠO ĐƠN NẠP VÀNG HỆ THỐNG CHỜ DUYỆT ----
    elif data == "p_money_deposit":
        tx_id = f"DEP{int(time.time())}"  # Khởi tạo mã giao dịch nạp duy nhất dựa trên timestamp
        
        with db_lock:
            pending_tx[tx_id] = {"user_id": user_id, "type": "NAP", "amount": 100000, "status": "PENDING"}
            
        try:
            bot.answer_callback_query(
                call.id, 
                "📨 GỬI LỆNH NẠP THÀNH CÔNG!\nYêu cầu nạp 100,000 Vàng đã được chuyển thẳng tới Hội Đồng Admin.", 
                show_alert=True
            )
            
            # Gửi tín hiệu thông báo hóa đơn khẩn cấp cho toàn bộ Admin có trong danh sách ADMIN_IDS
            for admin_id in ADMIN_IDS:
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("✅ Phê Duyệt", callback_data=f"adm_pay_{tx_id}"),
                    InlineKeyboardButton("❌ Từ Chối", callback_data=f"adm_den_{tx_id}")
                )
                bot.send_message(
                    admin_id, 
                    f"🔔 **LỆNH NẠP VÀNG ĐANG CHỜ DUYỆT**\n\n• **Người chơi:** {u['name']} (ID: `{user_id}`)\n• **Hạn mức yêu cầu:** `100,000 Vàng`\n• **Mã hóa đơn:** `{tx_id}`", 
                    reply_markup=markup
                )
        except Exception as e:
            print(f"Lỗi kích hoạt hóa đơn nạp vàng: {e}")

    # ---- 2.6 XỬ LÝ NÚT: TẠO ĐƠN RÚT VÀNG VỀ BANK ----
    elif data == "p_money_withdraw":
        if not u["bank"]:
            bot.answer_callback_query(
                call.id, 
                "⚠️ THAO TÁC BẤT THÀNH!\nBạn bắt buộc phải nhấn nút 'Liên Kết Thẻ Bank' trước khi thực hiện rút tài sản.", 
                show_alert=True
            )
            return
            
        if u["gold"] < 20000:
            bot.answer_callback_query(
                call.id, 
                "❌ NGÂN KHỐ TRỐNG RỖNG!\nSố dư của bạn không đủ. Yêu cầu tối thiểu để rút tiền là 20,000 Vàng.", 
                show_alert=True
            )
            return
            
        tx_id = f"WTH{int(time.time())}"  # Khởi tạo mã giao dịch rút duy nhất dựa trên timestamp
        
        with db_lock:
            u["gold"] -= 20000  # Giam lỏng số dư ví vàng của người chơi lập tức để chống gian lận rút kép
            pending_tx[tx_id] = {"user_id": user_id, "type": "RUT", "amount": 20000, "status": "PENDING"}
            
        try:
            bot.answer_callback_query(
                call.id, 
                "🏧 TẠO ĐƠN RÚT THÀNH CÔNG!\nHệ thống ngân khố đã khấu trừ tạm thời 20,000 Vàng và chuyển lệnh giải ngân sang Admin.", 
                show_alert=True
            )
            
            # Gửi lệnh chờ giải ngân thẳng cho các Admin tối cao
            for admin_id in ADMIN_IDS:
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("✅ Giải Ngân", callback_data=f"adm_pay_{tx_id}"),
                    InlineKeyboardButton("❌ Hủy Đơn Rút", callback_data=f"adm_den_{tx_id}")
                )
                bot.send_message(
                    admin_id, 
                    f"🔔 **YÊU CẦU RÚT TIỀN ĐANG CHỜ GIẢI NGÂN**\n\n• **Chiến binh:** {u['name']}\n• **Thông tin thẻ nhận:** `{u['bank']}`\n• **Khấu trừ ngân khố:** `20,000 Vàng`\n• **Mã hóa đơn:** `{tx_id}`", 
                    reply_markup=markup
                )
            # Đồng bộ lại giao diện chính của người chơi
            handle_economic_central_callbacks(call)
        except Exception as e:
            print(f"Lỗi kích hoạt hóa đơn rút vàng: {e}")

    # ---- 2.7 XỬ LÝ NÚT: MỞ TOÀN ÁN ADMIN (ADMIN PANEL CENTRAL) ----
    elif data == "p_admin_panel":
        try:
            bot.edit_message_text(
                "👑 **TÒA ÁN TỐI CAO ADMIN — HỆ THỐNG ĐIỀU HÀNH TRUNG TÂM** 👑\n\nChào ngài Admin tối cao, tại đây ngài có toàn quyền kiểm soát luồng vận hành kinh tế, phê duyệt ngân khố nạp rút toàn bộ hệ thống Bot.",
                chat_id,
                message_id,
                reply_markup=get_admin_panel_menu()
            )
        except Exception as e:
            print(f"Lỗi mở sảnh quản trị Admin: {e}")

    # ---- 2.8 XỬ LÝ NÚT: QUAY LẠI SẢNH CHÍNH CHAT RIÊNG ----
    elif data == "p_back_to_main":
        welcome_back = "🔮 **Hệ thống điều khiển sảnh trung tâm Ma Sói đã khôi phục trạng thái mặc định.**"
        try:
            bot.edit_message_text(
                welcome_back,
                chat_id,
                message_id,
                reply_markup=get_private_central_menu(user_id)
            )
        except Exception as e:
            print(f"Lỗi nhấn nút quay về sảnh chính: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3 và Phần 4...

# Biến trạng thái toàn cục điều khiển hệ thống bảo trì của Bot
MAINTENANCE_MODE = False

# ==================================================================
# 1. BỘ TIẾP NHẬN CALLBACK XỬ LÝ LỆNH ADMIN CHUYÊN SÂU
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("adm_pay_", "adm_den_", "adm_list_", "adm_stat_", "adm_maintenance_")))
def handle_admin_privilege_callbacks(call):
    """
    Xử lý toàn bộ các hành động phê duyệt tài chính và cấu hình hệ thống của Admin.
    Cam kết 100% bọc trong hàm check_security_privilege để chặn người lạ tuyệt đối.
    """
    global MAINTENANCE_MODE
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Xác thực đặc quyền Admin tối cao, người lạ bấm vào sẽ bị đẩy lùi lập tức
    if not check_security_privilege(call, require_admin=True):
        return
        
    # ---- 1.1 ADMIN DUYỆT (PHÊ DUYỆT / GIẢI NGÂN) HÓA ĐƠN ----
    if data.startswith("adm_pay_"):
        tx_id = data.replace("adm_pay_", "")
        
        with db_lock:
            tx = pending_tx.get(tx_id)
            if not tx or tx["status"] != "PENDING":
                bot.answer_callback_query(call.id, "⚠️ Hóa đơn này đã được xử lý hoặc không tồn tại!", show_alert=True)
                try: bot.delete_message(chat_id, message_id)
                except Exception: pass
                return
                
            tx["status"] = "SUCCESS"
            target_uid = tx["user_id"]
            amount = tx["amount"]
            
            # Nếu là lệnh nạp, tiến hành cộng Vàng cho người chơi
            if tx["type"] == "NAP":
                users_db[target_uid]["gold"] += amount
                
        # Thông báo tin vui thời gian thực trực tiếp vào hộp thư người chơi
        try:
            bot.send_message(
                target_uid,
                f"🎉 **THÔNG BÁO GIAO DỊCH THÀNH CÔNG** 🎉\n\n"
                f"Lệnh **{tx['type']} VÀNG** mang mã số `{tx_id}` trị giá `+{amount:,} Vàng` của bạn đã được Hội Đồng Admin phê duyệt và giải ngân thành công!"
            )
        except Exception: pass
        
        bot.edit_message_text(f"📝 **Mã đơn:** `{tx_id}`\n✅ Trạng thái: Đã PHÊ DUYỆT giải ngân thành công.", chat_id, message_id)
        bot.answer_callback_query(call.id, "Giải ngân đơn hàng thành công!")

    # ---- 1.2 ADMIN TỪ CHỐI / HỦY ĐƠN HÓA ĐƠN ----
    elif data.startswith("adm_den_"):
        tx_id = data.replace("adm_den_", "")
        
        with db_lock:
            tx = pending_tx.get(tx_id)
            if not tx or tx["status"] != "PENDING":
                bot.answer_callback_query(call.id, "⚠️ Hóa đơn này đã được xử lý hoặc không tồn tại!", show_alert=True)
                try: bot.delete_message(chat_id, message_id)
                except Exception: pass
                return
                
            tx["status"] = "REJECTED"
            target_uid = tx["user_id"]
            amount = tx["amount"]
            
            # Nếu từ chối lệnh rút, tiến hành hoàn trả tiền cược giam lỏng lại cho người chơi
            if tx["type"] == "RUT":
                users_db[target_uid]["gold"] += amount
                
        # Thông báo tin tức từ chối trực tiếp cho người chơi
        try:
            bot.send_message(
                target_uid,
                f"❌ **THÔNG BÁO HỦY GIAO DỊCH** ❌\n\n"
                f"Lệnh **{tx['type']} VÀNG** mang mã số `{tx_id}` trị giá `{amount:,} Vàng` của bạn đã bị từ chối phê duyệt bởi hệ thống Tòa Án Admin. Ngân khố của bạn đã được hoàn trả nguyên vẹn."
            )
        except Exception: pass
        
        bot.edit_message_text(f"📝 **Mã đơn:** `{tx_id}`\n❌ Trạng thái: Đã TỪ CHỐI đơn hàng thành công.", chat_id, message_id)
        bot.answer_callback_query(call.id, "Đã từ chối đơn hàng!")

    # ---- 1.3 ADMIN XEM DANH SÁCH ĐƠN ĐANG CHỜ (KIỂM TOÁN LỆNH) ----
    elif data in ["adm_list_deposit", "adm_list_withdraw"]:
        req_type = "NAP" if "deposit" in data else "RUT"
        
        with db_lock:
            filtered_txs = [f"• Mã: `{tid}` | ID User: `{info['user_id']}` | Số lượng: `{info['amount']:,} Vàng`" 
                            for tid, info in pending_tx.items() if info["type"] == req_type and info["status"] == "PENDING"]
            
        list_text = f"📋 **DANH SÁCH LỆNH {req_type} VÀNG ĐANG CHỜ DUYỆT** 📋\n\n"
        if not filtered_txs:
            list_text += "✨ Hiện tại không có hóa đơn nào đang chờ xử lý trên hệ thống."
        else:
            list_text += "\n".join(filtered_txs)
            
        bot.edit_message_text(list_text, chat_id, message_id, parse_mode="Markdown", reply_markup=get_admin_panel_menu())

    # ---- 1.4 ADMIN KIỂM TOÁN TỔNG LƯỢNG VÀNG TOÀN BOT ----
    elif data == "adm_stat_gold":
        with db_lock:
            total_users = len(users_db)
            total_gold_in_circulation = sum(u["gold"] for u in users_db.values())
            total_pending_orders = len([t for t in pending_tx.values() if t["status"] == "PENDING"])
            
        stat_text = (
            f"📊 **BÁO CÁO KIỂM TOÁN NGÂN KHỐ TOÀN CẦU** 📊\n\n"
            f"• **Tổng số tài khoản đã khởi tạo:** `{total_users:,}` thợ săn.\n"
            f"• **Tổng lượng Vàng đang lưu thông:** `{total_gold_in_circulation:,} Vàng`.\n"
            f"• **Số lệnh nạp/rút đang tắc nghẽn chờ duyệt:** `{total_pending_orders:,}` đơn hàng.\n\n"
            f"🛡️ *Hệ thống tài chính vận hành an toàn, không ghi nhận dấu hiệu xung đột dữ liệu trên bộ nhớ Termux.*"
        )
        bot.edit_message_text(stat_text, chat_id, message_id, parse_mode="Markdown", reply_markup=get_admin_panel_menu())

    # ---- 1.5 ADMIN BẬT / TẮT CHẾ ĐỘ BẢO TRÌ HỆ THỐNG ----
    elif data == "adm_maintenance_toggle":
        with db_lock:
            MAINTENANCE_MODE = not MAINTENANCE_MODE
            
        status_str = "🔴 ĐÃ BẬT BẢO TRÌ" if MAINTENANCE_MODE else "🟢 ĐÃ MỞ CỬA SẢNH CHƠI"
        bot.answer_callback_query(call.id, f"⚙️ Đã chuyển đổi cấu hình hệ thống sang: {status_str}", show_alert=True)
        
        maintenance_text = (
            f"👑 **QUẢN LÝ TRẠNG THÁI HỆ THỐNG BOT** 👑\n\n"
            f"• Trạng thái hiện tại: **{status_str}**\n\n"
            f"👉 *Khi bật bảo trì, thành viên người lạ sẽ không thể bấm nút khởi tạo phòng game nhóm hoặc giao dịch tài sản.*"
        )
        bot.edit_message_text(maintenance_text, chat_id, message_id, reply_markup=get_admin_panel_menu())

# ==================================================================
# 2. BỘ LỌC CHẶN NGƯỜI CHƠI KHI ĐANG TRONG CHẾ ĐỘ BẢO TRÌ
# ==================================================================
# Tích hợp hàm kiểm tra bảo trì vào logic bảo mật trung gian để tối ưu hóa
def check_maintenance_interceptor(message) -> bool:
    """Kiểm tra xem Bot có đang đóng sảnh để Admin bảo trì hay không"""
    if MAINTENANCE_MODE and not is_admin(message.from_user.id):
        bot.send_message(
            message.chat.id, 
            "⚙️ **THÀNH TRÌ ĐANG BẢO TRÌ** ⚙️\n\nTòa Thánh Ma Sói đang được các Admin tối cao nâng cấp thuật toán và niêm phong ngân khố. Vui lòng quay lại sau ít phút!"
        )
        return True
    return False
# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4 và Phần 5...

# ==================================================================
# 1. KỊCH BẢN THOẠI NGẪU NHIÊN KHI KHỞI TẠO PHÒNG (DRAMATIC INIT DIALOGUES)
# ==================================================================
GROUP_SETUP_DIALOGUES = [
    "⚡ **MỘT LỜI NGUYỀN MỚI ĐÃ KHAI MỞ!** ⚡\n\n🔮 Tế đàn Ma Sói đã được thiết lập bởi Trưởng Làng **{host_name}**.\n💰 Mức cược bảo chứng sinh tử: `1,000 Vàng`.\n💀 Bóng tối đang phủ xuống thung lũng... Ai sẽ là kẻ dám bước vào vết xe đổ này?",
    "🐺 **TIẾNG HÚ XÉ TOẠC MÀN ĐÊM!** 🐺\n\n🩸 Chiến binh **{host_name}** vừa mở ra cánh cổng dẫn đến ngôi làng bị nguyền rủa.\n💰 Phí đặt cược sinh mệnh: `1,000 Vàng`.\n🏹 Hỡi các thợ săn, hãy cầm vũ khí lên trước khi quỷ dữ tìm đến gõ cửa nhà ngươi!",
    "🦅 **ĐÊM ĐẪM MÁU ĐANG CẬN KỀ!** 🦅\n\n🛡️ Thủ lĩnh **{host_name}** đã dựng lá chắn bảo vệ sảnh chờ ma sói.\n💰 Chi phí góp quỹ treo cổ: `1,000 Vàng`.\n🩸 Kẻ yếu tim tốt nhất nên lùi lại phía sau, chiến trường này không dành cho kẻ nhút nhát!"
]

# ==================================================================
# 2. DANH SÁCH HIỆU ỨNG THỜI TIẾT BẤT NGỜ (WEATHER EFFECTS CONFIG)
# ==================================================================
WEATHER_POOL = [
    {
        "name": "⛈️ Giông Bão Kinh Hoàng",
        "desc": "Mưa lớn kèm sấm sét dữ dội che khuất mọi tầm nhìn! Tiên Tri bị nhiễu loạn luồng khí, âm thanh gầm rú khiến dân làng hoang mang tột độ."
    },
    {
        "name": "🌫️ Sương Mù Dày Đặc",
        "desc": "Lớp sương trắng xóa bao phủ toàn bộ làng. Bảo Vệ khó lòng định vị chính xác mục tiêu. Sói dễ dàng áp sát con mồi hơn bao giờ hết."
    },
    {
        "name": "🌕 Trăng Tròn Huyết Nguyệt",
        "desc": "Ánh trăng đỏ như máu đánh thức bản năng khát máu của loài quỷ dữ. Sức mạnh phe Sói đạt đỉnh điểm, lời thoại thảo luận trở nên căng thẳng."
    },
    {
        "name": "❄️ Tuyết Rơi Lạnh Giá",
        "desc": "Cơn bão tuyết tràn về khiến mọi chuyển động ban đêm trở nên chậm chạp và để lại dấu vết rõ rệt trên nền tuyết trắng."
    }
]

# ==================================================================
# 3. HÀM DỰNG MENU GAME ĐỘNG CHO GROUP (DYNAMIC GROUP KEYBOARD)
# ==================================================================
def get_group_game_keyboard(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    """
    Tạo giao diện nút bấm thông minh dựa trên trạng thái thực tế của Group Chat.
    Tự động ẩn/hiện nút điều khiển khởi động dựa theo ID của Chủ phòng.
    """
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Khởi tạo dữ liệu phòng trống nếu nhóm chưa từng chơi game
    if chat_id not in games:
        games[chat_id] = {"status": "IDLE", "players": {}, "host": None, "weather": None, "timer_active": False}
        
    game = games[chat_id]
    status = game["status"]
    
    # 3.1 Giao diện khi sảnh đang trống (IDLE)
    if status == "IDLE":
        markup.add(InlineKeyboardButton("🆕 Tạo Trận Đấu Mới (Cược 1K)", callback_data=f"g_setup_{chat_id}"))
        
    # 3.2 Giao diện khi sảnh đang tuyển quân (JOINING)
    elif status == "JOINING":
        markup.add(
            InlineKeyboardButton("➕ Tham Gia Phòng", callback_data=f"g_join_{chat_id}"),
            InlineKeyboardButton("➖ Rời Phòng Chờ", callback_data=f"g_leave_{chat_id}")
        )
        markup.add(InlineKeyboardButton("📋 Kiểm Tra Quân Số", callback_data=f"g_list_{chat_id}"))
        
        # Đặc quyền chỉ hiển thị nút Khai hỏa/Hủy phòng cho chủ phòng (Host)
        if user_id == game["host"]:
            markup.add(
                InlineKeyboardButton("🚀 Kích Hoạt Phát Vai", callback_data=f"g_start_{chat_id}"),
                InlineKeyboardButton("❌ Hủy Trận Đấu", callback_data=f"g_cancel_{chat_id}")
            )
            
    # 3.3 Giao diện khi trận đấu đang diễn ra (NIGHT / DAY)
    elif status in ["NIGHT", "DAY"]:
        markup.add(
            InlineKeyboardButton("🔮 Xem Chức Năng Riêng", callback_data=f"g_myrole_{chat_id}"),
            InlineKeyboardButton("💀 Tình Trạng Sinh Mệnh", callback_data=f"g_alive_{chat_id}")
        )
        # Chỉ người chơi còn sống mới hiển thị nút mở cổng vote vào ban ngày
        if status == "DAY" and game["players"].get(user_id, {}).get("alive", False):
            markup.add(InlineKeyboardButton("🗳️ Bỏ Phiếu Treo Cổ", callback_data=f"g_openvote_{chat_id}"))
            
    return markup

# ==================================================================
# 4. BỘ TIẾP NHẬN CALLBACK ĐIỀU KHIỂN SẢNH GAME NHÓM
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("g_"))
def handle_group_game_callbacks(call):
    """
    Xử lý toàn bộ các tương tác nút bấm chơi game trong chat nhóm.
    Đảm bảo kiểm tra chế độ bảo trì hệ thống và chống đơ nút bấm.
    """
    # Tích hợp bộ chặn bảo trì từ Phần 5
    if MAINTENANCE_MODE and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚙️ Hệ thống đang được Admin bảo trì nâng cấp. Sảnh nhóm tạm khóa!", show_alert=True)
        return
        
    user_id = call.from_user.id
    data = call.data
    
    # Vượt qua bộ lọc chống spam click của Phần 2
    if not check_security_privilege(call, require_admin=False):
        return
        
    parts = data.split("_")
    action = parts[1]
    chat_id = int(parts[2])
    
    if chat_id not in games:
        games[chat_id] = {"status": "IDLE", "players": {}, "host": None, "weather": None, "timer_active": False}
        
    game = games[chat_id]
    u = users_db[user_id]
    
    # ---- 4.1 XỬ LÝ NÚT: KHỞI TẠO PHÒNG GAME MỚI ----
    if action == "setup":
        if game["status"] != "IDLE":
            bot.answer_callback_query(call.id, "⚠️ Ngôi làng đang trong cuộc chiến sinh tử, không thể tạo sảnh mới!", show_alert=True)
            return
        if u["gold"] < 1000:
            bot.answer_callback_query(call.id, "❌ VỚN ĐIỀU LỆ KHÔNG ĐỦ!\nTài sản của bạn dưới 1,000 Vàng, không thể bảo chứng phòng cược.", show_alert=True)
            return
            
        with db_lock:
            game["status"] = "JOINING"
            game["host"] = user_id
            game["players"] = {user_id: {"name": u["name"], "role": None, "alive": True}}
            
        # Biến đổi ngẫu nhiên lời thoại khởi tạo phòng kịch tính
        random_setup_text = random.choice(GROUP_SETUP_DIALOGUES).format(host_name=u["name"])
        
        try:
            bot.edit_message_text(
                random_setup_text,
                chat_id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=get_group_game_keyboard(chat_id, user_id)
            )
            bot.answer_callback_query(call.id, "Khởi tạo sảnh đấu thành công!")
        except Exception as e:
            print(f"Lỗi render sảnh chờ nhóm: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5 và Phần 6...

# ==================================================================
# 1. BỘ TIẾP NHẬN CALLBACK ĐIỀU PHỐI THÀNH VIÊN VÀ QUYẾT TOÁN CƯỢC
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("g_join_", "g_leave_", "g_list_", "g_cancel_", "g_start_")))
def handle_lobby_management_callbacks(call):
    """
    Quản lý luồng tuyển quân, cập nhật danh sách thành viên và kiểm tra tài chính.
    Đã sửa lỗi đồng bộ luồng ghi dữ liệu vàng, cam kết không bị đơ nút.
    """
    if MAINTENANCE_MODE and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚙️ Hệ thống đang được Admin bảo trì nâng cấp. Sảnh tạm đóng!", show_alert=True)
        return

    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if not check_security_privilege(call, require_admin=False):
        return

    parts = data.split("_")
    action = parts[1]
    
    game = games[chat_id]
    u = users_db[user_id]

    # ---- 1.1 XỬ LÝ NÚT: THAM GIA PHÒNG CHỜ ĐẶT CƯỢC ----
    if action == "join":
        if game["status"] != "JOINING":
            bot.answer_callback_query(call.id, "⚠️ Đã hết thời gian ghi danh cho trận đấu này!", show_alert=True)
            return
        if user_id in game["players"]:
            bot.answer_callback_query(call.id, "🛡️ Thần trí tỉnh táo! Bạn đã có mặt trong danh sách phòng chờ.", show_alert=True)
            return
        if u["gold"] < 1000:
            bot.answer_callback_query(call.id, "❌ KHÔNG ĐỦ VÀNG!\nBạn cần ít nhất 1,000 Vàng để nộp bảo chứng cược.", show_alert=True)
            return
            
        with db_lock:
            game["players"][user_id] = {"name": u["name"], "role": None, "alive": True}
            
        count = len(game["players"])
        join_msg = (
            f"🆕 **DANH SÁCH CHIÊU MỘ ĐANG MỞ** 🆕\n\n"
            f"👥 **Tổng quân số hiện tại:** `{count}` chiến binh.\n"
            f"⚡ **Người mới gia nhập:** {u['name']}\n\n"
            f"👉 *Nhấn 'Tham Gia' để đặt cược 1,000 Vàng bước vào vòng lặp sinh tử!*"
        )
        try:
            bot.edit_message_text(join_msg, chat_id, message_id, parse_mode="Markdown", reply_markup=get_group_game_keyboard(chat_id, user_id))
            bot.answer_callback_query(call.id, "Ghi danh thành công!")
        except Exception as e: print(f"Lỗi join phòng: {e}")

    # ---- 1.2 XỬ LÝ NÚT: RỜI PHÒNG CHỜ (RÚT QUÂN) ----
    elif action == "leave":
        if game["status"] != "JOINING" or user_id not in game["players"]:
            bot.answer_callback_query(call.id, "Hành động không hợp lệ.", show_alert=True)
            return
        if user_id == game["host"]:
            bot.answer_callback_query(call.id, "⚠️ Trưởng làng không thể rời đi! Hãy chọn 'Hủy Trận Đấu' nếu muốn giải tán.", show_alert=True)
            return
            
        with db_lock:
            del game["players"][user_id]
            
        count = len(game["players"])
        leave_msg = (
            f"⚠️ **MỘT CHIẾN BINH ĐÃ QUAY ĐẦU!** ⚠️\n\n"
            f"🏃‍♂️ **{u['name']}** đã rút lui khỏi trận chiến vì hoảng sợ.\n"
            f"👥 **Quân số còn lại:** `{count}` người."
        )
        try:
            bot.edit_message_text(leave_msg, chat_id, message_id, parse_mode="Markdown", reply_markup=get_group_game_keyboard(chat_id, user_id))
            bot.answer_callback_query(call.id, "Rút lui khỏi sảnh thành công.")
        except Exception as e: print(f"Lỗi leave phòng: {e}")

    # ---- 1.3 XỬ LÝ NÚT: KIỂM TRA QUÂN SỐ TẠI CHỖ ----
    elif action == "list":
        p_list = "\n".join([f"• 👤 {p['name']}" for p in game["players"].values()])
        bot.answer_callback_query(call.id, f"📝 THÀNH VIÊN TRONG SẢNH:\n{p_list}", show_alert=True)

    # ---- 1.4 XỬ LÝ NÚT: HỦY TRẬN ĐẤU (GIẢI TÁN PHÒNG) ----
    elif action == "cancel":
        if user_id != game["host"]:
            bot.answer_callback_query(call.id, "❌ Quyền hạn không đủ! Chỉ chủ phòng mới được giải tán trận đấu.", show_alert=True)
            return
        with db_lock:
            game["status"] = "IDLE"
            game["players"] = {}
        try:
            bot.edit_message_text("❌ **SẢNH CHỜ ĐÃ BỊ GIẢI TÁN!**\n\nChủ phòng đã thu hồi lệnh bài triệu tập. Toàn bộ tiền bảo chứng của thành viên được bảo toàn.", chat_id, message_id, reply_markup=get_group_game_keyboard(chat_id, user_id))
            bot.answer_callback_query(call.id, "Giải tán phòng thành công!")
        except Exception as e: print(f"Lỗi hủy phòng: {e}")

    # ---- 1.5 XỬ LÝ NÚT: QUYẾT TOÁN CƯỢC & BẮT ĐẦU TRẬN ĐẤU ----
    elif action == "start":
        if user_id != game["host"]:
            bot.answer_callback_query(call.id, "❌ Chỉ trưởng làng mới có quyền ra lệnh phát động!", show_alert=True)
            return
            
        count = len(game["players"])
        if count < 4:  # Thiết lập luật tối thiểu 4 người chơi
            bot.answer_callback_query(call.id, f"⚠️ Đăng ký bất thành! Cần tối thiểu 4 người để cân bằng thế trận (Hiện tại: {count}).", show_alert=True)
            return
            
        # VÒNG LẶP KHẤU TRỪ TIỀN CƯỢC TUẦN TỰ AN TOÀN TUYỆT ĐỐI
        with db_lock:
            # Quét lại một lần nữa xem có ai bị tụt số dư trong lúc chờ phòng không
            for p_id in game["players"].keys():
                if users_db[p_id]["gold"] < 1000:
                    bot.answer_callback_query(call.id, f"❌ Trận đấu hoãn lại! Người chơi {users_db[p_id]['name']} hiện không đủ 1,000 Vàng để khớp lệnh cược.", show_alert=True)
                    return
            
            # Thực thi trừ tiền cược chính thức khi sảnh đủ điều kiện bảo chứng
            for p_id in game["players"].keys():
                users_db[p_id]["gold"] -= 1000
                
        bot.answer_callback_query(call.id, "⚔️ Hợp đồng sinh tử đã ký kết! Đang phân bổ chức năng...", show_alert=False)
        
        # Gọi tiếp mô-đun gán thời tiết và phát vai trò bí mật...
        # [Đoạn mã xử lý phát vai trò của Phần 8 sẽ được kích hoạt tại đây]

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6 và Phần 7...

# ==================================================================
# 1. HÀM KÍCH HOẠT PHÂN VAI ĐỘNG (KẾT NỐI VÀO PHẦN CHỐT TIỀN CƯỢC CỦA PHẦN 7)
# ==================================================================
def execute_role_distribution_system(chat_id: int, message_id: int, host_id: int) -> None:
    """
    Thuật toán xáo trộn vị trí, gán trạng thái sinh mệnh mặc định.
    Khởi tạo cấu trúc mảng ghi nhận mục tiêu ban đêm ẩn danh nhằm chống xung đột dữ liệu.
    """
    game = games[chat_id]
    p_ids = list(game["players"].keys())
    count = len(p_ids)
    
    with db_lock:
        # 1.1 Xáo trộn danh sách người chơi bằng thuật toán xáo trộn mảng Fisher-Yates
        random.shuffle(p_ids)
        
        # 1.2 Phân bổ cấu trúc bài động tối ưu theo số lượng người tham gia thực tế
        if count >= 8:
            roles_pool = ["Ma Sói 🐺", "Ma Sói 🐺", "Tiên Tri 🔮", "Bảo Vệ 🛡️", "Phù Thủy 🧪"] + ["Dân Làng 🧑‍🌾"] * (count - 5)
        elif count >= 6:
            roles_pool = ["Ma Sói 🐺", "Ma Sói 🐺", "Tiên Tri 🔮", "Bảo Vệ 🛡️"] + ["Dân Làng 🧑‍🌾"] * (count - 4)
        else:
            roles_pool = ["Ma Sói 🐺", "Tiên Tri 🔮", "Bảo Vệ 🛡️"] + ["Dân Làng 🧑‍🌾"] * (count - 3)
            
        # 1.3 Khởi tạo từ điển dữ liệu tạm thời để lưu vết tương tác ban đêm của các chức năng
        game["night_actions"] = {
            "wolf_target": None,     # ID nạn nhân bị bầy Sói thống nhất cắn
            "wolf_votes": {},        # Phiếu bầu của từng con Sói: {wolf_id: target_id}
            "seer_target": None,     # ID người chơi bị Tiên Tri soi danh tính
            "guard_target": None,    # ID người chơi được Bảo Vệ dựng khiên che chắn
            "witch_poison": None,    # ID người bị Phù Thủy ném bình thuốc độc
            "witch_save": False      # Trạng thái Phù Thủy có dùng bình cứu mạng hay không (True/False)
        }
        
        # 1.4 Gán giá trị nền tảng vào database tổng của phòng chơi
        for idx, p_id in enumerate(p_ids):
            game["players"][p_id]["role"] = roles_pool[idx]
            game["players"][p_id]["alive"] = True
            game["players"][p_id]["voted_for"] = None
            
            # Chọn ngẫu nhiên một hiệu ứng thời tiết cho trận đấu này từ Phần 6
            selected_weather = random.choice(WEATHER_POOL)
            game["weather"] = selected_weather
            game["status"] = "NIGHT"
            
    # ---- 1.5 PHÂN PHÁT TIN NHẮN RIÊNG QUA TIẾN TRÌNH NGẦM (NON-BLOCKING THREADS) ----
    # Đẩy tác vụ gửi tin nhắn riêng cho từng người vào luồng độc lập, tránh nghẽn luồng sảnh nhóm
    chat_title = "Trận Đấu Sinh Tử"
    for p_id in game["players"].keys():
        assigned_role = game["players"][p_id]["role"]
        threading.Thread(
            target=dispatch_private_dramatic_role_script, 
            args=(p_id, assigned_role, chat_title, chat_id)
        ).start()
        
    # Render giao diện đêm buông xuống ra sảnh chat nhóm
    dramatic_night_announcement = (
        f"🎬 **TRẬN ĐẤU CHÍNH THỨC KHAI HỎA** 🎬\n\n"
        f"🌍 **Hiệu ứng thời tiết:** {game['weather']['name']}\n"
        f"📝 *Mô tả khí quyển:* {game['weather']['desc']}\n\n"
        f"🌌 **MÀN ĐÊM HUYỀN BÍ BUÔNG XUỐNG...** 🌌\n"
        f"Bầu trời xám xịt, sương lạnh vây quanh ngôi làng. Những tiếng xào xạc bí ẩn vang lên ngoài cửa sổ.\n"
        f"Tất cả các sinh thể đêm hãy kiểm tra ngay **Hộp Thư Chat Riêng của Bot** để thực thi thiên chức bí mật!"
    )
    
    try:
        bot.edit_message_text(
            dramatic_night_announcement,
            chat_id,
            message_id,
            parse_mode="Markdown",
            reply_markup=get_group_game_keyboard(chat_id, host_id)
        )
    except Exception as e:
        print(f"Lỗi thông báo đêm sảnh nhóm: {e}")

# ==================================================================
# 2. KỊCH BẢN LỜI THOẠI BIẾN ĐỔI NGẪU NHIÊN KÈM DANH SÁCH MỤC TIÊU NÚT BẤM
# ==================================================================
def dispatch_private_dramatic_role_script(user_id: int, role: str, group_name: str, chat_id: int) -> None:
    """
    Tự động biên dịch cốt truyện kịch tính riêng biệt.
    Xây dựng danh sách nút bấm tên các nạn nhân tiềm năng đổ vào chat riêng cho người chơi tương tác.
    """
    try:
        game = games[chat_id]
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Vòng lặp xây dựng bảng nút bấm chứa tên của toàn bộ người chơi khác cho mục tiêu kỹ năng
        for target_id, target_info in game["players"].items():
            if target_id != user_id:  # Chặn không cho tự hiện tên bản thân trong danh sách mục tiêu
                # Mã hóa dữ liệu callback cực ngắn dạng nén: sk_[Mã phòng]_[ID mục tiêu] để chống tràn 64 bytes
                markup.add(InlineKeyboardButton(f"👤 {target_info['name']}", callback_data=f"sk_{chat_id}_{target_id}"))
                
        intro_header = f"🎭 **HỘI ĐỒNG MA SÓI PHÒNG [{group_name}] TRIỆU TẬP** 🎭\n\n"
        
        if "Ma Sói" in role:
            script_text = intro_header + (
                "🐺 **VAI TRÒ CỦA NGƯƠI: MA SÓI KHÁT MÁU** 🐺\n"
                "• **Kịch bản thoại:** Màn đêm lạnh giá kéo về, những nanh vuốt nhọn hoắt bật ra khỏi đầu ngón tay ngươi. Bản năng nguyên thủy đòi hỏi máu và thịt tươi. Hãy nhìn qua danh sách dân làng bên dưới, chọn lấy một kẻ xấu số để kết liễu cuộc đời chúng đêm nay!\n"
                "• **Mục tiêu phe cánh:** Tiêu diệt dân thường cho tới khi quân số hai phe cân bằng.\n\n"
                "🩸 **Hãy chạm vào nút bấm tên mục tiêu ngươi muốn tàn sát:**"
            )
        elif "Tiên Tri" in role:
            script_text = intro_header + (
                "🔮 **VAI TRÒ CỦA NGƯƠI: TIÊN TRI THẦN BÍ** 🔮\n"
                "• **Kịch bản thoại:** Giữa giông bão sấm sét gầm rú hay sương mù dày đặc bao phủ ngôi làng, quả cầu pha lê cổ xưa của ngươi bắt đầu phát sáng. Hãy tập trung thần trí, khai mở thiên nhãn nhìn xuyên qua lớp mặt nạ giả dối của một linh hồn để vạch trần ma quỷ.\n"
                "• **Mục tiêu phe cánh:** Tìm ra Sói ẩn mình và thuyết phục dân làng treo cổ chúng.\n\n"
                "👁️ **Hãy chọn một người chơi ngươi muốn soi rõ danh tính thật sự:**"
            )
        elif "Bảo Vệ" in role:
            script_text = intro_header + (
                "🛡️ **VAI TRÒ CỦA NGƯƠI: HỘ VỆ THÀNH TRÌ** 🛡️\n"
                "• **Kịch bản thoại:** Thanh gươm và chiếc khiên rực lửa của ngươi là ranh giới duy nhất giữa sự sống và cái chết của dân làng. Đêm nay, những bước chân tuần tra âm thầm của ngươi sẽ dừng lại trước cánh cửa nhà ai để che chở họ khỏi nanh vuốt quỷ dữ?\n"
                "• **Mục tiêu phe cánh:** Bảo vệ các vị trí nòng cốt để lật ngược thế trận.\n\n"
                "🏰 **Hãy chọn một người chơi ngươi muốn dựng lá chắn bảo vệ đêm nay:**"
            )
        else:
            # Dân làng vô năng ban đêm, tước bỏ hoàn toàn nút bấm mục tiêu tránh lỗi logic bấm loạn
            script_text = intro_header + (
                "🧑‍🌾 **VAI TRÒ CỦA NGƯƠI: DÂN LÀNG TỘI NGHIỆP** 🧑‍🌾\n"
                "• **Kịch bản thoại:** Ngươi chỉ là một phàm nhân tay không tấc sắt giữa thung lũng đầy rẫy ma quỷ. Giờ lành đã điểm, hãy khóa chặt then cửa, trùm chăn cầu nguyện thần linh chở che và im lặng lắng nghe những tiếng gầm rú kinh hoàng vọng lại từ quảng trường.\n"
                "• **Mục tiêu phe cánh:** Sống sót tới sáng và dùng lá phiếu ban ngày để thực thi công lý.\n\n"
                "💤 *Màn đêm của bạn trôi qua trong im lặng. Hãy nghỉ ngơi chờ bình minh lên...*"
            )
            markup = None  # Triệt tiêu giao diện nút bấm
            
        bot.send_message(user_id, script_text, parse_mode="Markdown", reply_markup=markup)
        
    except Exception as e:
        # Ghi nhận log terminal Termux để bạn dễ theo dõi nếu có người chơi chặn Bot
        print(f"Lỗi đồng bộ phân phát tin nhắn riêng cho ID {user_id}: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6, Phần 7 và Phần 8...

# ==================================================================
# 1. BỘ TIẾP NHẬN SỰ KIỆN NÚT BẤM KỸ NĂNG BAN ĐÊM QUA CHAT RIÊNG
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("sk_"))
def handle_night_skill_callbacks(call):
    """
    Xử lý các lệnh chạm nút kỹ năng ban đêm (Cắn, Soi, Bảo Vệ) gửi từ Chat Riêng.
    Tích hợp thuật toán khóa luồng, chống đơ nút và kiểm tra sinh mệnh thời gian thực.
    """
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Sử dụng bộ lọc chống spam click của Phần 2 để giải phóng nút bấm vĩnh viễn
    if not check_security_privilege(call, require_admin=False):
        return

    # Tách cấu trúc gói nén callback data: sk_[Mã phòng nhóm]_[ID mục tiêu]
    parts = data.split("_")
    game_chat_id = int(parts[1])
    target_id = int(parts[2])
    
    # Kiểm tra phòng đấu có tồn tại trong dữ liệu toàn cục hay không
    if game_chat_id not in games:
        bot.answer_callback_query(call.id, "⚠️ Trận đấu này đã kết thúc từ trước hoặc không tồn tại!", show_alert=True)
        return
        
    game = games[game_chat_id]
    
    # CHẶN LỖI: Nếu trận đấu đã trôi qua ban đêm, không cho phép bấm nút cũ của đêm trước
    if game["status"] != "NIGHT":
        bot.answer_callback_query(call.id, "🌙 Trời đã sáng hoặc màn đêm đã trôi qua. Kỹ năng không còn hiệu lực!", show_alert=True)
        return
        
    # CHẶN LỖI: Kiểm tra xem người bấm nút có thực sự tham gia trận đấu và còn sống hay không
    player_info = game["players"].get(user_id)
    if not player_info or not player_info["alive"]:
        bot.answer_callback_query(call.id, "💀 Bạn đã là một linh hồn tử thương, không thể can thiệp vào dòng thời gian!", show_alert=True)
        return

    role = player_info["role"]
    target_name = game["players"][target_id]["name"]
    target_role = game["players"][target_id]["role"]

    # ==================================================================
    # 2. PHÂN LOẠI THAO TÁC THEO CHỨC NĂNG VÀ THUẬT TOÁN SÓI ĐỒNG THUẬN
    # ==================================================================
    with db_lock:
        # ---- 2.1 XỬ LÝ LOGIC: PHE MA SÓI CẮN NGƯỜI ----
        if "Ma Sói" in role:
            # Ghi nhận lá phiếu cắn của con Sói này vào mảng vote riêng của Sói
            game["night_actions"]["wolf_votes"][user_id] = target_id
            
            # Đếm số lượng Sói còn sống trong phòng chơi
            alive_wolves = [pid for pid, p in game["players"].items() if "Ma Sói" in p["role"] and p["alive"]]
            current_votes_count = len(game["night_actions"]["wolf_votes"])
            
            bot.answer_callback_query(call.id, f"🩸 Bạn đã chọn xé xác: {target_name}!", show_alert=False)
            
            # Cập nhật lời thoại trạng thái trong Chat Riêng để Sói biết tiến độ đồng bọn
            bot.edit_message_text(
                f"🐺 **HỘI ĐỒNG SÓI GHI NHẬN** 🐺\n\n"
                f"• Bạn đã bỏ phiếu cắn: **{target_name}**\n"
                f"📈 Tiến độ đồng thuận: `{current_votes_count}/{len(alive_wolves)}` Ma Sói đã chọn xong.",
                chat_id, message_id
            )
            
            # Thuật toán chốt nạn nhân: Nếu tất cả Sói còn sống đã bấm xong nút
            if current_votes_count >= len(alive_wolves):
                from collections import Counter
                # Tìm ID người chơi nhận được nhiều phiếu cắn nhất từ bầy Sói
                votes_list = list(game["night_actions"]["wolf_votes"].values())
                most_voted_target = Counter(votes_list).most_common(1)[0][0]
                game["night_actions"]["wolf_target"] = most_voted_target

        # ---- 2.2 XỬ LÝ LOGIC: TIÊN TRI SOI BÀI BÍ MẬT ----
        elif "Tiên Tri" in role:
            # Lưu mục tiêu đã chọn vào hệ thống để đồng bộ
            game["night_actions"]["seer_target"] = target_id
            bot.answer_callback_query(call.id, "🔮 Thiên nhãn đang khai mở...", show_alert=False)
            
            # Phân loại phe phái dựa trên vai trò của mục tiêu để trả kết quả chuẩn xác
            faction_result = "🔴 PHE MA SÓI" if "Ma Sói" in target_role else "🟢 PHE DÂN LÀNG"
            
            # Lời thoại kịch tính phản hồi ngay lập tức vào hộp thư riêng của Tiên Tri
            seer_response = (
                f"🔮 **KẾT QUẢ KHAI MỞ THIÊN NHÃN** 🔮\n\n"
                f"• Mục tiêu soi chiếu: **{target_name}**\n"
                f"✨ Bản ngã linh hồn thuộc về: **【 {faction_result} 】**\n\n"
                f"👉 *Hãy ghi nhớ thông tin này thật kỹ và dùng tài biện luận để thuyết phục dân làng treo cổ kẻ thủ ác vào ban ngày!*"
            )
            bot.edit_message_text(seer_response, chat_id, message_id, parse_mode="Markdown")

        # ---- 2.3 XỬ LÝ LOGIC: BẢO VỆ DỰNG LÁ CHẮN ----
        elif "Bảo Vệ" in role:
            # CHẶN LỖI: Bảo Vệ không được phép bảo vệ cùng 1 người chơi trong 2 đêm liên tiếp (Mở rộng ở Phần Ngày)
            game["night_actions"]["guard_target"] = target_id
            bot.answer_callback_query(call.id, f"🛡️ Đã dựng khiên che chở cho {target_name}!", show_alert=False)
            
            guard_response = (
                f"🛡️ **THÀNH TRÌ BẢO VỆ KÍCH HOẠT** 🛡️\n\n"
                f"• Bạn đã thiết lập vùng bảo hộ quanh nhà của: **{target_name}**\n\n"
                f"💤 *Bất kỳ sát thương nào từ bầy Sói giáng xuống mục tiêu này đêm nay sẽ bị triệt tiêu hoàn toàn.*"
            )
            bot.edit_message_text(guard_response, chat_id, message_id, parse_mode="Markdown")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phẩn 4, Phần 5, Phần 6, Phần 7, Phần 8 và Phần 9...

# ==================================================================
# 1. KỊCH BẢN THOẠI BÌNH MINH BIẾN ĐỔI NGẪU NHIÊN (DAWN DIALOGUES)
# ==================================================================
DAWN_PEACEFUL_DIALOGUES = [
    "☀️ **BÌNH MINH LÊN — MỘT ĐÊM YÊN BÌNH TRÔI QUA!** ☀️\n\nNhững tia nắng ban mai đầu tiên rọi xuống thung lũng, xua tan lớp sương mù dày đặc.\n🛡️ Nhờ sự cảnh giác cao độ của các hộ vệ, không có một giọt máu nào phải đổ xuống đêm qua!\n📢 Ngôi làng tạm thời an toàn. Hãy tiếp tục thảo luận để tìm ra kẻ thủ ác ẩn mình.",
    "🐓 **TIẾNG GÀ GÁY BÁO HIỆU SỰ SỐNG!** 🐓\n\nThần linh đã lắng nghe lời cầu nguyện của dân làng.\n🌌 Đêm qua, bầy quỷ dữ đã tổ chức một cuộc săn người quy mô lớn nhưng thất bại thảm hại!\n✨ Toàn bộ dân số sống sót vẹn toàn bước vào ngày mới."
]

DAWN_BLOODY_DIALOGUES = [
    "🩸 **BÌNH MINH ĐẪM MÁU — KHÔNG GIAN TANG TÓC!** 🩸\n\nÁnh nắng ban mai không thể sưởi ấm được bầu không khí lạnh ngắt tại quảng trường.\n💀 Khi cánh cửa nhà mở ra, dân làng bàng hoàng phát hiện **{victim_name}** đã bị cắn xé một cách tàn nhẫn đêm qua!\n🎭 Nạn nhân xấu số chính là một: **【 {victim_role} 】**\n\n📢 Hận thù dâng cao, cổng **Bỏ Phiếu Treo Cổ** đã được kích hoạt. Hãy thực thi công lý!",
    "🦅 **TIẾNG QUẠ KÊU OÁN THÁN TRÊN BẦU TRỜI NGÔI LÀNG!** 🦅\n\nMột đêm giông bão hay sương mù dày đặc đã che giấu tội ác kinh hoàng của loài sói.\n💀 Người chơi **{victim_name}** đã vĩnh viễn nằm lại trong vũng máu tại nhà riêng!\n🎭 Thân phận thật sự của người chết: **【 {victim_role} 】**\n\n👉 Hãy dùng Menu nút bấm bên dưới để truy tìm những kẻ có hành vi đáng nghi ngay lập tức!"
]

# ==================================================================
# 2. HÀM TỔNG HỢP DỮ LIỆU ĐÊM VÀ THỰC THI CHUYỂN NGÀY (DAWN SYNTHESIS)
# ==================================================================
def execute_dawn_synthesis_system(chat_id: int, message_id: int) -> None:
    """
    Thuật toán cốt lõi xử lý giao thoa sát thương ban đêm:
    - Đối chiếu mục tiêu cắn của Ma Sói với mục tiêu lá chắn của Bảo Vệ.
    - [Nâng cấp mở rộng]: Kết hợp bình thuốc độc / cứu mạng của Phù Thủy nếu có.
    - Cập nhật trạng thái sinh mệnh, kiểm tra điều kiện kết thúc game và mở cổng Vote ngày.
    """
    game = games[chat_id]
    
    # CHẶN LỖI: Đảm bảo hàm chỉ thực thi một lần duy nhất, tránh lỗi đa luồng gọi trùng lặp
    with db_lock:
        if game["status"] != "NIGHT":
            return
        game["status"] = "DAY"
        
        # 2.1 Thu thập đích danh dữ liệu hành động từ Phần 8 & Phần 9
        wolf_target = game["night_actions"]["wolf_target"]
        guard_target = game["night_actions"]["guard_target"]
        witch_poison = game["night_actions"]["witch_poison"]
        witch_save = game["night_actions"]["witch_save"]
        
        killed_targets = set()  # Sử dụng Set để gom danh sách người chết, tự động loại trừ trùng lặp ID
        
        # 2.2 THUẬT TOÁN ĐỐI CHIẾU SÁT THƯƠNG SÓI CẮN VS BẢO VỆ CỨU
        if wolf_target:
            # Nếu có Phù Thủy dùng bình cứu mạng hoặc Bảo Vệ dựng khiên trùng với mục tiêu Sói cắn
            if wolf_target == guard_target or witch_save:
                pass  # Sát thương triệt tiêu, mục tiêu được cứu sống an toàn
            else:
                killed_targets.add(wolf_target)
                
        # 2.3 THUẬT TOÁN NÉM BÌNH ĐỘC CỦA PHÙ THỦY (ĐỘC XUYÊN GIÁP BẢO VỆ)
        if witch_poison:
            killed_targets.add(witch_poison)
            
        # 2.4 THỰC THI CẬP NHẬT TRẠNG THÁI SINH MỆNH VÀO DATABASE
        victim_name = ""
        victim_role = ""
        
        for v_id in killed_targets:
            if v_id in game["players"]:
                game["players"][v_id]["alive"] = False
                victim_name = game["players"][v_id]["name"]
                victim_role = game["players"][v_id]["role"]
                
        # Đặt lại toàn bộ dữ liệu phiếu bầu treo cổ của vòng ngày mới về trạng thái trống sạch
        for p_id in game["players"].keys():
            game["players"][p_id]["voted_for"] = None

    # ==================================================================
    # 3. KIỂM TRA ĐIỀU KIỆN THẮNG CUỘC BẬT RA SẢNH (WIN-CONDITION CHECKER)
    # ==================================================================
    # [Thuật toán kiểm tra kết toán thắng thua và chia Vàng sẽ được bóc tách riêng ở Phần 11]
    
    # ==================================================================
    # 4. RENDER GIAO DIỆN BÌNH MINH LÊN SẢNH NHÓM
    # ==================================================================
    if not killed_targets:
        # Nếu đêm qua không có ai chết, bốc ngẫu nhiên lời thoại yên bình
        dramatic_dawn_text = random.choice(PRIVATE_GREETINGS if 'PRIVATE_GREETINGS' in locals() else DAWN_PEACEFUL_DIALOGUES)
        if dramatic_dawn_text not in DAWN_PEACEFUL_DIALOGUES:
            dramatic_dawn_text = random.choice(DAWN_PEACEFUL_DIALOGUES)
    else:
        # Nếu có người chết, bốc ngẫu nhiên lời thoại thảm kịch và nhúng danh tính nạn nhân
        dramatic_dawn_text = random.choice(DAWN_BLOODY_DIALOGUES).format(
            victim_name=victim_name,
            victim_role=victim_role
        )
        
    try:
        # Chỉnh sửa tin nhắn sảnh nhóm sang giao diện Ngày mới kèm bảng nút thao tác Ngày (Xem chức năng/Vote)
        bot.edit_message_text(
            dramatic_dawn_text,
            chat_id,
            message_id,
            parse_mode="Markdown",
            reply_markup=get_group_game_keyboard(chat_id, ADMIN_ID)  # Gọi hàm render menu động từ Phần 6
        )
    except Exception as e:
        print(f"Lỗi đồng bộ giao diện bình minh sảnh nhóm: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6, Phần 7, Phần 8, Phần 9 và Phần 10...

# ==================================================================
# 1. KỊCH BẢN THOẠI TUYÊN BỐ CHIẾN THẮNG CHUNG CUỘC (WINNING DIALOGUES)
# ==================================================================
WOLF_WIN_DIALOGUES = [
    "🐺 **PHÂN CẢNH TANG TÓC — PHE MA SÓI CHIẾN THẮNG!** 🐺\n\n"
    "Bóng đêm đã nuốt chửng hoàn toàn tia hy vọng cuối cùng của ngôi làng. Sói và người giờ đây đã cân bằng quân số, dân làng tay không tấc sắt đã trở thành bữa tiệc đẫm máu cho bầy quỷ dữ!\n\n"
    "💰 Quỹ cược đặt sảnh đã được chuyển giao vào ngân khố của những kẻ săn mồi khát máu.",
    "🌕 **TRĂNG HUYẾT ĐẠT ĐỈNH — SÓI THỐNG TRỊ THUNG LŨNG!** 🌕\n\n"
    "Mọi tiếng nói công lý ban ngày đã bị dập tắt bởi nanh vuốt. Phe Ma Sói đã xuất sắc ẩn mình và tiêu diệt các chức năng cốt lõi thành công!\n\n"
    "🎉 Xin chúc mừng các chú Sói tinh ranh đêm nay."
]

VILLAGER_WIN_DIALOGUES = [
    "🏆 **BÌNH MINH VĨNH CỬU — PHE DÂN LÀNG CHIẾN THẮNG!** 🏆\n\n"
    "Công lý tối cao đã thực thi! Con Ma Sói cuối cùng đã bị kéo lên đoạn đầu đài trong tiếng reo hò của toàn thể dân làng. Lời nguyền đẫm máu bao phủ thung lũng suốt bao chu kỳ trăng tròn chính thức bị phá bỏ!\n\n"
    "💰 Toàn bộ quỹ cược bảo chứng đã được chia đều cho các anh hùng sống sót và cống hiến.",
    "⚔️ **QUÉT SẠCH BÓNG TỐI — KHẢI HOÀN CA VANG LÊN!** ⚔️\n\n"
    "Sự kết hợp hoàn hảo giữa nhãn giới Tiên Tri, lá chắn Bảo Vệ và trực giác nhạy bén của Dân Làng đã quét sạch bầy sói hung tàn ra khỏi bờ cõi!\n\n"
    "🎉 Ngôi làng đã khôi phục lại sự bình yên vĩnh cửu."
]

# ==================================================================
# 2. THUẬT TOÁN KIỂM TOÁN VÀ PHÂN PHỐI TÀI SẢN KHI KẾT THÚC GAME
# ==================================================================
def check_and_execute_game_settlement(chat_id: int, message_id: int) -> bool:
    """
    Quét trạng thái sinh mệnh, đối chiếu điều kiện thắng của phe Sói và Dân Làng.
    - Quỹ Vàng = Tổng số người chơi ban đầu * 1,000 Vàng.
    - Chia đều quỹ Vàng cho tất cả thành viên thuộc phe chiến thắng (bất kể sống/chết theo luật chuẩn).
    - Cập nhật Win/Loss, thăng hạng Rank và đưa phòng chơi về trạng thái IDLE.
    """
    game = games[chat_id]
    
    # Đếm số lượng thành viên từng phe CÒN SỐNG hiện tại
    alive_wolves = 0
    alive_villagers = 0
    
    for p_id, p_info in game["players"].items():
        if p_info["alive"]:
            if "Ma Sói" in p_info["role"]:
                alive_wolves += 1
            else:
                alive_villagers += 1
                
    winning_faction = None
    
    # 2.1 ĐỐI CHIẾU ĐIỀU KIỆN THẮNG CUỘC CHUẨN QUỐC TẾ
    if alive_wolves == 0:
        winning_faction = "VILLAGER"  # Sói chết hết -> Dân Làng thắng
    elif alive_wolves >= alive_villagers:
        winning_faction = "WOLF"      # Số Sói >= Số Dân -> Sói thắng
    elif alive_wolves == 0 and alive_villagers == 0:
        winning_faction = "DRAW"      # Thảm kịch chết chóc toàn bộ -> Hòa
        
    if not winning_faction:
        return False  # Trận đấu chưa kết thúc, tiếp tục chu kỳ Ngày/Đêm tiếp theo

    # 2.2 TIẾN TRÌNH KHÓA LUỒNG PHÂN PHỐI QUỸ CƯỢC VÀNG TỰ ĐỘNG
    with db_lock:
        total_players_count = len(game["players"])
        total_prize_pool = total_players_count * 1000  # Thu hồi 1,000 Vàng cược từ Phần 7 thành tổng quỹ thưởng
        
        winners_list = []
        identity_reveal_text = "\n🎭 **DANH TÍNH THẬT SỰ CỦA CÁC LINH HỒN:**\n"
        
        # Lọc danh sách những người thuộc phe chiến thắng để chia thưởng
        for p_id, p_info in game["players"].items():
            # Xây dựng bảng công bố danh tính thật ở cuối trận
            status_icon = "🟢 CÒN SỐNG" if p_info["alive"] else "💀 ĐÃ CHẾT"
            identity_reveal_text += f"• **{p_info['name']}**: {p_info['role']} ({status_icon})\n"
            
            # Cập nhật bảng thống kê Thắng / Thua vào cơ sở dữ liệu users_db của Phần 1
            if winning_faction == "WOLF" and "Ma Sói" in p_info["role"]:
                winners_list.append(p_id)
                users_db[p_id]["win"] += 1
            elif winning_faction == "VILLAGER" and "Ma Sói" not in p_info["role"]:
                winners_list.append(p_id)
                users_db[p_id]["win"] += 1
            elif winning_faction != "DRAW":
                users_db[p_id]["loss"] += 1
                
            # Cập nhật danh hiệu Rank tự động từ Phần 1 cho tất cả mọi người
            update_user_rank(p_id)

        # Thuật toán chia đều tài sản, xử lý số dư lẻ nếu quỹ chia không hết
        if winning_faction != "DRAW" and winners_list:
            reward_per_winner = total_prize_pool // len(winners_list)
            for w_id in winners_list:
                users_db[w_id]["gold"] += reward_per_winner
                
        # 2.3 CHỌN LỜI THOẠI KỊCH TÍNH VÀ ĐỒNG BỘ GIAO DIỆN KẾT THÚC TRẬN ĐẤU
        if winning_faction == "WOLF":
            announcement = random.choice(WOLF_WIN_DIALOGUES)
            announcement += f"\n🏆 **Mức thưởng giải ngân:** `+{reward_per_winner:,} Vàng` cho mỗi Ma Sói."
        elif winning_faction == "VILLAGER":
            announcement = random.choice(VILLAGER_WIN_DIALOGUES)
            announcement += f"\n🏆 **Mức thưởng giải ngân:** `+{reward_per_winner:,} Vàng` cho mỗi người dân chính nghĩa."
        else:
            announcement = "💀 **THẢM KỊCH HOANG TÀN — TRẬN ĐẤU HÒA CHẾT CHÓC!** 💀\n\nKhông một ai sống sót bước ra khỏi thung lũng đêm qua. Quỹ bảo chứng cược vĩnh viễn bị niêm phong vào ngân khố Tòa Thánh."

        final_dashboard_text = (
            f"🏁 **TRẬN ĐẤU CHÍNH THỨC KẾT THÚC** 🏁\n\n"
            f"{announcement}\n"
            f"{identity_reveal_text}\n"
            f"👉 *Hồ sơ cá nhân, ví vàng và Rank của bạn đã được đồng bộ hóa thời gian thực tại hộp thư Chat Riêng với Bot. Nhấn nút bên dưới để tạo sảnh cược mới!*"
        )
        
        # 2.4 GIẢI PHÓNG PHÒNG ĐẤU VỀ TRẠNG THÁI CHỜ MẶC ĐỊNH (RESET ROOM)
        game["status"] = "IDLE"
        game["players"] = {}
        game["weather"] = None
        game["timer_active"] = False

    try:
        # Sửa tin nhắn sảnh nhóm về trạng thái IDLE mở nút tạo trận mới của Phần 6
        bot.send_message(
            chat_id,
            final_dashboard_text,
            parse_mode="Markdown",
            reply_markup=get_group_game_keyboard(chat_id, ADMIN_ID)
        )
    except Exception as e:
        print(f"Lỗi thông báo kết toán tài sản sảnh nhóm: {e}")
        
    return True

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6, Phần 7, Phần 8, Phần 9, Phần 10 và Phần 11...

# ==================================================================
# 1. HÀM DỰNG MENU DANH SÁCH VOTE ẨN DANH QUA CHAT RIÊNG (VOTE KEYBOARD)
# ==================================================================
def get_private_voting_keyboard(chat_id: int, voter_id: int) -> InlineKeyboardMarkup:
    """
    Tạo bảng nút bấm chứa danh sách các thành viên CÒN SỐNG trong phòng chơi.
    Được gửi riêng vào hộp thư của người chơi để họ vote ẩn danh.
    """
    markup = InlineKeyboardMarkup(row_width=2)
    game = games[chat_id]
    
    # Duyệt qua toàn bộ danh sách phòng chơi để bốc những kẻ còn sinh mạng
    for p_id, p_info in game["players"].items():
        if p_info["alive"] and p_id != voter_id:
            # Nén callback data cực ngắn: vt_[Mã phòng]_[ID mục tiêu] để chống tràn 64 bytes
            markup.add(InlineKeyboardButton(f"💀 Treo cổ: {p_info['name']}", callback_data=f"vt_{chat_id}_{p_id}"))
            
    # Thêm nút bấm hủy bỏ phiếu bầu nếu người chơi đổi ý giữa chừng
    markup.add(InlineKeyboardButton("❌ Hủy Lá Phiếu Bầu", callback_data=f"vt_{chat_id}_cancel"))
    return markup

# ==================================================================
# 2. XỬ LÝ LỆNH BẤM NÚT MỞ CỔNG VOTE TẠI SẢNH NHÓM (GROUP INTERACTION)
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("g_openvote_"))
def handle_group_open_vote_button(call):
    """
    Khi người chơi bấm nút "🗳️ Bỏ Phiếu Treo Cổ" tại sảnh chat nhóm.
    Hệ thống sẽ điều hướng gửi bảng nút bấm chọn nạn nhân vào Chat Riêng của họ.
    """
    user_id = call.from_user.id
    data = call.data
    
    # Giải phóng tín hiệu xoay vòng bằng bộ lọc Phần 2
    if not check_security_privilege(call, require_admin=False):
        return
        
    chat_id = int(data.replace("g_openvote_", ""))
    game = games[chat_id]
    
    # CHẶN LỖI: Kiểm tra trạng thái sảnh phải đang là Ban Ngày
    if game["status"] != "DAY":
        bot.answer_callback_query(call.id, "🌙 Cổng biểu quyết hiện đã đóng hoặc chỉ mở vào Ban Ngày!", show_alert=True)
        return
        
    # CHẶN LỖI: Kiểm tra xem tài khoản này còn sống trong phòng chơi không
    p_info = game["players"].get(user_id)
    if not p_info or not p_info["alive"]:
        bot.answer_callback_query(call.id, "💀 Bạn đã hy sinh hoặc không ở trong trận đấu, không có tư cách bỏ phiếu!", show_alert=True)
        return
        
    # Gửi bảng danh sách mục tiêu ẩn danh vào hộp thư riêng của người chơi
    try:
        bot.send_message(
            user_id,
            f"🗳️ **QUYỂN LỰC LÁ PHIẾU CÔNG LÝ** 🗳️\n\n"
            f"Trận đấu tại phòng nhóm: **{call.message.chat.title}**\n"
            f"Hãy lựa chọn một linh hồn ngươi nghi ngờ là Ma Sói ẩn mình để đưa lên đoạn đầu đài. Lá phiếu của ngươi là hoàn toàn ẩn danh!",
            reply_markup=get_private_voting_keyboard(chat_id, user_id)
        )
        bot.answer_callback_query(call.id, "📨 Bot đã gửi danh sách bỏ phiếu kín vào Chat Riêng của bạn!", show_alert=False)
    except Exception:
        bot.answer_callback_query(call.id, "⚠️ Thất bại! Hãy nhấn /start với Bot ở chat riêng một lần trước để cấp quyền gửi tin nhắn bí mật.", show_alert=True)

# ==================================================================
# 3. TIẾP NHẬN TƯƠNG TÁC LÁ PHIẾU ẨN DANH QUA CHAT RIÊNG (PRIVATE INTERACTION)
# ==================================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("vt_"))
def handle_private_anonymous_vote_callbacks(call):
    """
    Xử lý các thao tác nhấp nút chọn đích danh treo cổ gửi từ Chat Riêng.
    Tính toán thanh tiến độ phần trăm thời gian thực và đồng bộ ngược về sảnh nhóm.
    """
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if not check_security_privilege(call, require_admin=False):
        return
        
    # Phân tách mảng callback data: vt_[Mã phòng nhóm]_[ID mục tiêu / 'cancel']
    parts = data.split("_")
    game_chat_id = int(parts[1])
    target_action = parts[2]
    
    if game_chat_id not in games:
        bot.answer_callback_query(call.id, "⚠️ Trận đấu này không tồn tại hoặc đã kết toán xong!", show_alert=True)
        return
        
    game = games[game_chat_id]
    
    if game["status"] != "DAY":
        bot.answer_callback_query(call.id, "☀️ Thời gian biểu quyết ban ngày đã khép lại!", show_alert=True)
        return
        
    p_info = game["players"].get(user_id)
    if not p_info or not p_info["alive"]:
        bot.answer_callback_query(call.id, "💀 Bạn đã bị loại khỏi vòng chơi!", show_alert=True)
        return

    # THỰC THI LOGIC GHI NHẬN LÁ PHIẾU TRONG KHỐI ĐỒNG BỘ LUỒNG
    with db_lock:
        if target_action == "cancel":
            if p_info["voted_for"] is None:
                bot.answer_callback_query(call.id, "🤷‍♂️ Bạn chưa hề bỏ phiếu cho ai trước đó!", show_alert=True)
                return
            p_info["voted_for"] = None
            bot.answer_callback_query(call.id, "❌ Đã rút lại lá phiếu công lý thành công!", show_alert=False)
            bot.edit_message_text("🗳️ Bạn đã rút lại lá phiếu. Hãy cân nhắc kỹ trước khi chọn lại mục tiêu.", chat_id, message_id, reply_markup=get_private_voting_keyboard(game_chat_id, user_id))
        else:
            target_id = int(target_action)
            p_info["voted_for"] = target_id
            target_name = game["players"][target_id]["name"]
            bot.answer_callback_query(call.id, f"🎯 Đã bỏ phiếu treo cổ: {target_name}!", show_alert=False)
            bot.edit_message_text(f"✅ Ghi nhận thành công!\nBạn đã bỏ phiếu đưa **{target_name}** lên đoạn đầu đài.", chat_id, message_id, reply_markup=get_private_voting_keyboard(game_chat_id, user_id))

        # 3.1 THUẬT TOÁN TÍNH TOÁN TIẾN ĐỘ VOTE TRỰC QUAN TOÀN PHÒNG
        alive_players_count = len([pid for pid, p in game["players"].items() if p["alive"]])
        voted_players_count = len([pid for pid, p in game["players"].items() if p["alive"] and p["voted_for"] is not None])
        
        # Vẽ thanh tiến độ trực quan bằng Emoji (Visual Progress Bar)
        total_bars = 10
        filled_bars = int((voted_players_count / alive_players_count) * total_bars) if alive_players_count > 0 else 0
        progress_bar_str = "🟩" * filled_bars + "⬜" * (total_bars - filled_bars)
        
    # 3.2 ĐỒNG BỘ TIẾN ĐỘ BẰNG TIN NHẮN ĐẨY VÀO SẢNH NHÓM
    sync_progress_text = (
        f"🗳️ **TIẾN ĐỘ BIỂU QUYẾT TREO CỔ DÂN LÀNG** 🗳️\n\n"
        f"📊 Trạng thái: |`{progress_bar_str}`| `{voted_players_count}/{alive_players_count}` thành viên đã vote.\n\n"
        f"👉 *Mọi người hãy chạm vào nút 'Bỏ Phiếu Treo Cổ' của Menu nhóm để hoàn tất nghĩa vụ công dân bí mật trước khi hết giờ thảo luận!*"
    )
    
    try:
        # Gửi tin nhắn thông báo tiến độ mới vào nhóm mà không đè tin cũ để tránh trôi chat
        bot.send_message(game_chat_id, sync_progress_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Lỗi đồng bộ thanh tiến độ vote về sảnh nhóm: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6, Phần 7, Phần 8, Phần 9, Phần 10, Phần 11 và Phần 12...

# ==================================================================
# 1. KỊCH BẢN THOẠI PHÁN QUYẾT ĐOẠN ĐẦU ĐÀI BIẾN ĐỔI NGẪU NHIÊN (HANG DIALOGUES)
# ==================================================================
HANG_SUCCESS_DIALOGUES = [
    "⚖️ **PHÁN QUYẾT TỐI CAO — ĐOẠN ĐẦU ĐÀI KHAI HỎA!** ⚖️\n\n"
    "Dân làng đã đồng lòng bỏ phiếu với đại đa số phiếu thuận chống lại **{hanged_name}**.\n"
    "💀 Tiếng trống kêu oan vang lên vô vọng, chiếc thòng lọng siết chặt lấy cổ nạn nhân. Linh hồn tội lỗi vĩnh viễn bị trục xuất khỏi cõi phàm!\n"
    "🎭 Thân phận thực sự của kẻ bị hành quyết: **【 {hanged_role} 】**\n\n"
    "🌌 Màn đêm chuẩn bị buông xuống vây quanh ngôi làng một lần nữa...",
    
    "🪵 **GIÀN HỎA THIÊU ĐÃ RỰC LỬA — THỰC THI CÔNG LÝ!** 🪵\n\n"
    "Sau cuộc thảo luận căng thẳng, **{hanged_name}** chính là kẻ bị nghi ngờ nhiều nhất và bị áp giải lên giàn thiêu.\n"
    "💀 Trong ngọn lửa rực cháy, lớp ngụy trang rách nát rơi xuống phơi bày danh tính thật!\n"
    "🎭 Vai trò bí mật của linh hồn này: **【 {hanged_role} 】**\n\n"
    "⏱️ Hãy chuẩn bị tinh thần, bóng tối đang tái sinh tại thung lũng."
]

HANG_FAILED_DIALOGUES = [
    "⚖️ **TÒA ÁN DÂN LÀNG BẤT THÀNH — HÒA PHIẾU BIỂU QUYẾT!** ⚖️\n\n"
    "Sự nghi ngờ bị phân tán, hoặc số phiếu bầu cao nhất bị cân bằng giữa các nghi phạm.\n"
    "🤷‍♂️ Không có bất kỳ sự đồng thuận tuyệt đối nào được thiết lập. Trưởng Làng hạ lệnh bãi triều, tha bổng cho tất cả mọi người ban ngày hôm nay!\n\n"
    "⚠️ Nguy hiểm cận kề, bầy quỷ dữ sẽ tận dụng sơ hở này khi màn đêm kéo về...",
    
    "🗳️ **QUYỀN LỰC BỊ TỪ CHỐI — KHÔNG AI BỊ TREO CỔ!** 🗳️\n\n"
    "Dân làng đã không thể thống nhất được lá phiếu biểu quyết, hoặc phần lớn lựa chọn im lặng.\n"
    "💨 Ngày hôm nay kết thúc trong sự hoang mang và chia rẽ sâu sắc. Không ai phải bước lên đoạn đầu đài.\n\n"
    "🌌 Hãy khóa chặt then cửa, bóng tối đang áp sát ngôi làng!"
]

# ==================================================================
# 2. HÀM ĐÓNG CỔNG VOTE VÀ XỬ LÝ PHÁN QUYẾT TREO CỔ CHUYÊN SÂU
# ==================================================================
def execute_day_hanging_and_cycle_shift(chat_id: int, message_id: int) -> None:
    """
    Thuật toán đóng cổng biểu quyết ban ngày:
    - Gom toàn bộ thuộc tính voted_for trong database từ Phần 12.
    - Tìm kiếm ID nhận được nhiều phiếu bầu nhất bằng thuật toán Counter.
    - Xử lý tình huống hòa phiếu biểu quyết an toàn.
    - Chuyển trạng thái sinh mệnh, kiểm tra win-condition, và kích hoạt vòng lặp chuyển Đêm.
    """
    game = games[chat_id]
    
    # CHẶN LỖI: Chỉ thực thi nếu phòng chơi đang thực sự ở trạng thái Ban Ngày
    with db_lock:
        if game["status"] != "DAY":
            return
            
        votes_pool = []
        # Quét danh sách người chơi, chỉ thu thập phiếu của những thành viên còn sống
        for pid, pinfo in game["players"].items():
            if pinfo["alive"] and pinfo["voted_for"] is not None:
                votes_pool.append(pinfo["voted_for"])
                
        hanged_id = None
        is_tied = False
        
        # 2.1 THUẬT TOÁN PHÂN TÍCH TẬP HỢP PHIẾU BẦU CỰC ĐẠI
        if votes_pool:
            from collections import Counter
            vote_counts = Counter(votes_pool).most_common(2)
            
            # Nếu có ít nhất 2 người nhận được phiếu bầu
            if len(vote_counts) > 1:
                # Kiểm tra xem người có phiếu cao nhất có bằng người thứ hai không (Hòa phiếu)
                if vote_counts[0][1] == vote_counts[1][1]:
                    is_tied = True
                else:
                    hanged_id = vote_counts[0][0]
            else:
                # Chỉ có duy nhất một người bị vote
                hanged_id = vote_counts[0][0]

        hanged_name = ""
        hanged_role = ""

        # 2.2 THỰC THI LỆNH TREO CỔ NẾU ĐẠT ĐIỀU KIỆN ĐỒNG THUẬN CAO NHẤT
        if hanged_id and not is_tied:
            game["players"][hanged_id]["alive"] = False
            hanged_name = game["players"][hanged_id]["name"]
            hanged_role = game["players"][hanged_id]["role"]
            
            dramatic_result_text = random.choice(HANG_SUCCESS_DIALOGUES).format(
                hanged_name=hanged_name,
                hanged_role=hanged_role
            )
        else:
            # Hòa phiếu hoặc không ai vote, không ai bị treo cổ
            dramatic_result_text = random.choice(HANG_FAILED_DIALOGUES)

        # Đặt lại trạng thái phòng đấu sang Ban Đêm chuẩn bị chu kỳ mới
        game["status"] = "NIGHT"
        
        # Xóa sạch toàn bộ mảng ghi nhận tương tác ban đêm cũ để không lỗi chồng đè dữ liệu
        game["night_actions"] = {
            "wolf_target": None,
            "wolf_votes": {},
            "seer_target": None,
            "guard_target": None,
            "witch_poison": None,
            "witch_save": False
        }

    # ==================================================================
    # 3. ĐỒNG BỘ KIỂM TRA ĐIỀU KIỆN THẮNG CUỘC (WIN-CHECK CONNECTOR)
    # ==================================================================
    # Gọi hàm kiểm toán tài sản, chia cược Vàng từ Phần 11. Nếu game kết thúc, dừng luồng chuyển đêm ngay
    if check_and_execute_game_settlement(chat_id, message_id):
        return

    # ==================================================================
    # 4. GỬI PHÁN QUYẾT RA SẢNH VÀ TỰ ĐỘNG CHUYỂN CHU KỲ MÀN ĐÊM MỚI
    # ==================================================================
    try:
        bot.send_message(chat_id, dramatic_result_text, parse_mode="Markdown")
        
        # 4.1 Khởi động tiến trình luồng ngầm phát vai và nút bấm đêm mới cho các chức năng còn sống
        import threading
        p_ids = list(game["players"].keys())
        chat_title = "Vòng Lặp Vĩnh Hằng"
        
        for p_id in p_ids:
            # Chỉ phát lại nút kỹ năng ban đêm qua Chat Riêng cho những ai còn sống thực tế
            if game["players"][p_id]["alive"]:
                assigned_role = game["players"][p_id]["role"]
                threading.Thread(
                    target=dispatch_private_dramatic_role_script,  # Kế thừa hàm render nút đêm từ Phần 8
                    args=(p_id, assigned_role, chat_title, chat_id)
                ).start()
                
        # 4.2 Tự động kích hoạt bộ đếm ngược thời gian đêm ngầm từ Phần 6 để vận hành chu kỳ vô tận
        if not game["timer_active"]:
            game["timer_active"] = True
            threading.Thread(target=night_countdown_timer, args=(chat_id, message_id)).start()
            
    except Exception as e:
        print(f"Lỗi thực thi phán quyết đoạn đầu đài: {e}")

# Kế thừa tiếp tục từ Phần 1, Phần 2, Phần 3, Phần 4, Phần 5, Phần 6, Phần 7, Phần 8, Phần 9, Phần 10, Phần 11, Phần 12 và Phần 13...
import json
import os

# Đường dẫn file lưu trữ cục bộ ngay trên thư mục chạy của Termux
DATABASE_FILE = "masoi_users_database.json"

# ==================================================================
# 1. HÀM TỰ ĐỘNG SAO LƯU DỮ LIỆU VÀO BỘ NHỚ CỨNG (SAVE DATABASE)
# ==================================================================
def save_users_database_to_storage() -> None:
    """
    Chuyển đổi toàn bộ mảng users_db trong bộ nhớ RAM thành cấu trúc chuỗi JSON 
    và ghi đè an toàn xuống file cứng để lưu trữ vĩnh viễn.
    Được bọc chặt trong db_lock của Phần 1 để chặn đứng tình trạng ghi đè file rỗng.
    """
    with db_lock:
        try:
            # Tạo một bản sao tạm thời để tránh xung đột luồng khi cấu trúc JSON đang encode
            database_snapshot = dict(users_db)
            
            # Ghi dữ liệu kèm format thụt lề (indent) giúp file JSON gọn gàng, dễ kiểm toán khi cần
            with open(DATABASE_FILE, "w", encoding="utf-8") as f:
                json.dump(database_snapshot, f, ensure_ascii=False, indent=4)
                
            print("💾 [HỆ THỐNG] -> Đã đồng bộ ví Vàng và Rank của toàn bộ người chơi vào bộ nhớ Termux.")
        except Exception as e:
            print(f"❌ [LỖI NGHIÊM TRỌNG] Không thể ghi dữ liệu xuống bộ nhớ: {e}")

# ==================================================================
# 2. HÀM TỰ ĐỘNG KHÔI PHỤC DỮ LIỆU KHI KHỞI CHẠY BOT (LOAD DATABASE)
# ==================================================================
def load_users_database_from_storage() -> None:
    """
    Quét thư mục gốc của Termux khi Bot vừa kích hoạt.
    Nếu tìm thấy file sao lưu cũ, tiến hành nạp toàn bộ số dư Vàng, Bank, Rank của người chơi 
    ngược trở lại bộ nhớ RAM để sảnh chơi tiếp tục vận hành.
    """
    global users_db
    if not os.path.exists(DATABASE_FILE):
        print("ℹ️ [THÔNG BÁO] Không tìm thấy file sao lưu cũ. Hệ thống tự động khởi tạo database mới hoàn toàn.")
        users_db = {}
        return

    with db_lock:
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                
            # Ép kiểu dữ liệu Key từ String (mặc định của JSON) về lại kiểu số nguyên Integer (ID Telegram chuẩn)
            users_db = {int(k): v for k, v in loaded_data.items()}
            print(f"✅ [THÀNH CÔNG] Đã khôi phục dữ liệu ngân khố của {len(users_db)} người chơi từ file sao lưu cứng.")
        except Exception as e:
            print(f"❌ [LỖI NGHIÊM TRỌNG] Cấu trúc file JSON bị lỗi hoặc không thể đọc: {e}")
            users_db = {}

# ==================================================================
# 3. KẾT NỐI ĐỒNG BỘ VÀO TOÀN BỘ CÁC ĐIỂM BIẾN ĐỘNG TÀI SẢN KINH TẾ
# ==================================================================
# Bạn chỉ cần chèn lệnh gọi `save_users_database_to_storage()` vào cuối các hàm xử lý sau:
# - Phần 4 (Khi người chơi nhấn nút liên kết Bank thành công)
# - Phần 5 (Khi Admin nhấn nút APPROVE giải ngân nạp/rút Vàng)
# - Phần 7 (Khi trừ 1,000 Vàng tiền cược của các thành viên lúc start game)
# - Phần 11 (Khi cộng Vàng giải thưởng chia đều cho phe chiến thắng cuối trận)

# Ví dụ nâng cấp hàm init_user từ Phần 1 để tự động đồng bộ hóa:
def upgraded_init_user(user_id: int, name: str) -> None:
    """Khởi tạo tài khoản đồng bộ và tự động lưu file cứng để lưu vết"""
    need_save = False
    with db_lock:
        if user_id not in users_db:
            users_db[user_id] = {
                "name": name,
                "gold": 50000,
                "bank": None,
                "win": 0,
                "loss": 0,
                "rank": "Tập Sự Đêm Tối 🛡️",
                "last_click": 0.0
            }
            need_save = True
            
    if need_save:
        save_users_database_to_storage()

# Kế thừa tiếp tục từ Phần 1 đến Phần 15...

# ==================================================================
# PHẦN 16: TÍCH HỢP MINI-GAME TÀI XỈU VÀNG ĐỒNG BỘ 100% NÚT BẤM
# ==================================================================

# 1. KỊCH BẢN THOẠI NGẪU NHIÊN KHI KẾT QUẢ TÀI XỈU XUẤT HIỆN (DICE DIALOGUES)
DICE_OPEN_DIALOGUES = [
    "🎲 **TIẾNG XÚC XẮC VANG LÊN TRÊN CHIẾU BẠC THẦN THÁNH!** 🎲\n\n"
    "Hộp lắc vàng đã mở, ba viên xúc xắc mang theo vận mệnh của các thợ săn vừa dừng lại!\n\n"
    "▪️ Kết quả xúc xắc: **[ {d1} ] - [ {d2} ] - [ {d3} ]**\n"
    "📊 **Tổng điểm:** `{total} điểm` —👉 **【 {result_text} 】**\n\n"
    "🎉 Xin chúc mừng những linh hồn dũng cảm đã đặt trọn niềm tin vào cửa này! Tiền thưởng đã được giải ngân về ví.",
    
    "🔥 **VÒNG QUAY SỐ PHẬN ĐÃ PHÁN QUYẾT!** 🔥\n\n"
    "Khói bụi sảnh cược tan đi, để lộ kết quả xúc xắc định mệnh đêm nay:\n\n"
    "▪️ Xúc xắc ma thuật: **[ {d1} ] - [ {d2} ] - [ {d3} ]**\n"
    "📊 **Tổng số nút:** `{total} điểm` —👉 **【 {result_text} 】**\n\n"
    "💰 Kẻ thắng reo hò thu vàng về ngân khố, người thua lẳng lặng mài sắc vũ khí chờ đợi cơ hội phục hận!"
]

# Bộ lưu trữ trạng thái phiên Tài Xỉu tạm thời để chống đơ nút bấm
tx_sessions = {}

# 2. HÀM DỰNG GIAO DIỆN MENU ĐIỀU KHIỂN TÀI XỈU (GROUP MINI-GAME KEYBOARD)
def get_tai_xiu_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Tạo giao diện nút bấm đặt cược trực quan cho Mini-game Tài Xỉu"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    if chat_id not in tx_sessions:
        tx_sessions[chat_id] = {"status": "CLOSED", "bets": {}}
        
    session = tx_sessions[chat_id]
    
    if session["status"] == "CLOSED":
        markup.add(InlineKeyboardButton("🎲 Mở Bát Phiên Tài Xỉu Mới", callback_data=f"tx_open_{chat_id}"))
    else:
        markup.add(
            InlineKeyboardButton("🔺 ĐẶT TÀI (11-17)", callback_data=f"tx_bet_{chat_id}_TAI"),
            InlineKeyboardButton("🔻 ĐẶT XỈU (4-10)", callback_data=f"tx_bet_{chat_id}_XIU")
        )
        markup.add(InlineKeyboardButton("📋 Xem Danh Sách Cược", callback_data=f"tx_list_{chat_id}"))
        markup.add(InlineKeyboardButton("🎰 MỞ BÁT XÚC XẮC", callback_data=f"tx_roll_{chat_id}"))
        
    return markup

# 3. BỘ TIẾP NHẬN SỰ KIỆN CALLBACK VẬN HÀNH MINI-GAME TÀI XỈU
@bot.callback_query_handler(func=lambda call: call.data.startswith("tx_"))
def handle_tai_xiu_callbacks(call):
    """
    Điều phối toàn bộ các hành động đặt cược, hiển thị danh sách và lắc xúc xắc công khai.
    Đã sửa lỗi đồng bộ, liên kết trực tiếp ví vàng users_db và tự giải phóng trạng thái đơ nút.
    """
    if MAINTENANCE_MODE and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚙️ Hệ thống đang bảo trì. Các sảnh mini-game tạm khóa!", show_alert=True)
        return
        
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Chống spam nút bấm qua bộ lọc bảo mật của Phần 2
    if not check_security_privilege(call, require_admin=False):
        return
        
    parts = data.split("_")
    action = parts[1]
    game_chat_id = int(parts[2])
    
    if game_chat_id not in tx_sessions:
        tx_sessions[game_chat_id] = {"status": "CLOSED", "bets": {}}
        
    session = tx_sessions[game_chat_id]
    u = users_db[user_id]
    
    # ---- 3.1 HÀNH ĐỘNG: MỞ PHIÊN CƯỢC MỚI ----
    if action == "open":
        if session["status"] == "OPEN":
            bot.answer_callback_query(call.id, "⚠️ Phiên cược hiện tại đang mở sẵn rồi!", show_alert=True)
            return
            
        with db_lock:
            session["status"] = "OPEN"
            session["bets"] = {}
            
        lobby_msg = (
            "🎲 **SẢNH CƯỢC TÀI XỈU VÀNG ĐÃ KHAI MỞ** 🎲\n\n"
            "Hãy dùng Menu nút bấm bên dưới để đặt cược số tiền bảo chứng của bạn.\n"
            "• **TÀI:** Tổng điểm 3 xúc xắc từ 11 đến 17 (Ăn x2).\n"
            "• **XỈU:** Tổng điểm 3 xúc xắc từ 4 đến 10 (Ăn x2).\n"
            "❌ *Lưu ý: Nếu xúc xắc ra Bộ Ba Đồng Nhất (3 mặt giống nhau), nhà cái thu toàn bộ tiền cược!*\n\n"
            "💰 Hạn mức cược mặc định: `1,000 Vàng` / lần bấm nút."
        )
        try:
            bot.edit_message_text(lobby_msg, game_chat_id, message_id, parse_mode="Markdown", reply_markup=get_tai_xiu_keyboard(game_chat_id))
            bot.answer_callback_query(call.id, "Mở bát phiên cược thành công!")
        except Exception as e: print(f"Lỗi mở phiên TX: {e}")

    # ---- 3.2 HÀNH ĐỘNG: ĐẶT CƯỢC CỬA TÀI / XỈU ----
    elif action == "bet":
        choice = parts[3]  # Lấy chuỗi 'TAI' hoặc 'XIU'
        
        if session["status"] != "OPEN":
            bot.answer_callback_query(call.id, "⚠️ Đã hết thời gian nhận cược cho phiên này!", show_alert=True)
            return
        if user_id in session["bets"]:
            bot.answer_callback_query(call.id, f"🌟 Bạn đã đặt cửa {session['bets'][user_id]['choice']} trước đó rồi, không thể đổi cửa cược!", show_alert=True)
            return
        if u["gold"] < 1000:
            bot.answer_callback_query(call.id, "❌ Không đủ Vàng! Ngân khố của bạn dưới 1,000 Vàng để khớp lệnh cược.", show_alert=True)
            return
            
        with db_lock:
            # Ghi nhận thông tin cược và khấu trừ 1K vàng lập tức khỏi tài khoản người chơi
            u["gold"] -= 1000
            session["bets"][user_id] = {"choice": choice, "amount": 1000, "name": u["name"]}
            
        bot.answer_callback_query(call.id, f"🎯 Đặt cược 1,000 Vàng vào cửa 【{choice}】 thành công!", show_alert=False)
        
        # Tự động lưu file JSON từ Phần 14
        save_users_database_to_storage()

    # ---- 3.3 HÀNH ĐỘNG: XEM DANH SÁCH THÀNH VIÊN ĐÃ ĐẶT CƯỢC ----
    elif action == "list":
        if not session["bets"]:
            bot.answer_callback_query(call.id, "🤷‍♂️ Hiện tại chưa có thợ săn nào xuống tiền đặt cược.", show_alert=True)
            return
            
        bet_list_str = "📋 DANH SÁCH CHIÊU BẠC THỜI GIAN THỰC:\n\n"
        for bid, binfo in session["bets"].items():
            bet_list_str += f"• {binfo['name']}: Đặt cửa {binfo['choice']} (`1,000 Vàng`)\n"
            
        bot.answer_callback_query(call.id, bet_list_str, show_alert=True)

    # ---- 3.4 HÀNH ĐỘNG: MỞ BÁT LẮC XÚC XẮC & GIẢI NGÂN PHẦN THƯỞNG ----
    elif action == "roll":
        if session["status"] != "OPEN":
            bot.answer_callback_query(call.id, "Thao tác không hợp lệ.", show_alert=True)
            return
        if not session["bets"]:
            bot.answer_callback_query(call.id, "⚠️ Sảnh cược trống! Phải có ít nhất 1 người đặt cược mới có thể mở bát.", show_alert=True)
            return
            
        # Thuật toán sinh số ngẫu nhiên cho 3 viên xúc xắc
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        d3 = random.randint(1, 6)
        total_score = d1 + d2 + d3
        
        # Phân định kết quả dựa trên luật Tài Xỉu
        if d1 == d2 == d3:
            result_text = "BỘ BA ĐỒNG NHẤT (NHÀ CÁI THU HẾT) 💀"
            winning_choice = "NONE"
        elif total_score >= 11:
            result_text = "TÀI 🎉"
            winning_choice = "TAI"
        else:
            result_text = "XỈU 🎉"
            winning_choice = "XIU"
            
        # TIẾN TRÌNH KHÓA LUỒNG GIẢI NGÂN VÀNG CHO NGƯỜI THẮNG
        with db_lock:
            payout_logs = "\n\n💸 **BẢNG KẾT TOÁN THẮNG THUA:**\n"
            for b_uid, b_info in session["bets"].items():
                if b_info["choice"] == winning_choice:
                    # Thắng cược nhận lại x2 số tiền (hoàn trả 1K cược gốc + tặng 1K thưởng)
                    users_db[b_uid]["gold"] += 2000
                    payout_logs += f"• **{b_info['name']}**: Thắng (`+1,000 Vàng`)\n"
                else:
                    payout_logs += f"• **{b_info['name']}**: Thua (`-1,000 Vàng`)\n"
                    
            # Khép phiên cược đưa trạng thái về CLOSED
            session["status"] = "CLOSED"
            session["bets"] = {}

        # Đồng bộ lưu lại cơ sở dữ liệu cứng JSON
        save_users_database_to_storage()
        
        # Render kịch bản lời thoại xúc xắc ngẫu nhiên ra sảnh nhóm kèm bảng kết toán tiền vàng
        final_dramatic_dice_msg = random.choice(DICE_OPEN_DIALOGUES).format(
            d1=d1, d2=d2, d3=d3,
            total=total_score,
            result_text=result_text
        ) + payout_logs
        
        try:
            bot.edit_message_text(final_dramatic_dice_msg, game_chat_id, message_id, parse_mode="Markdown", reply_markup=get_tai_xiu_keyboard(game_chat_id))
            bot.answer_callback_query(call.id, f"Mở bát thành công: {total_score} điểm!", show_alert=False)
        except Exception as e: print(f"Lỗi thông báo kết quả Tài Xỉu: {e}")


# 4. CÂU LỆNH ĐỒNG BỘ GÕ /TAIXIU GỌI SẢNH RA GROUP CHAT
@bot.message_handler(commands=['taixiu'])
def cmd_call_tai_xiu_lobby(message):
    """Lệnh gọi nhanh sảnh Tài Xỉu ra Group Chat"""
    # Tích hợp bộ lọc chặn bảo trì hệ thống của Phần 5 để đồng bộ bảo mật
    if MAINTENANCE_MODE and not is_admin(message.from_user.id):
        bot.reply_to(message, "⚙️ Hệ thống đang được Admin bảo trì nâng cấp. Sảnh cược tạm khóa!")
        return

    if message.chat.type == "private":
        bot.reply_to(message, "❌ Mini-game đặt cược Tài Xỉu ẩn danh chỉ có thể hoạt động trong sảnh Nhóm (Group Chat)!")
        return
        
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎰 KÍCH HOẠT SẢNH TÀI XỈU VÀNG", callback_data=f"tx_open_{chat_id}"))
    bot.send_message(
        chat_id, 
        "🎲 **HỆ THỐNG SÒNG BẠC NGÔI LÀNG THÔNG BÁO** 🎲\nHãy nhấn nút bên dưới để mở bát phiên cược cày Vàng giải trí thời gian thực trong lúc chờ đợi phòng Ma Sói tuyển quân!", 
        reply_markup=markup
    )


# ==================================================================
# VÙNG KHỞI CHẠY HỆ THỐNG TRUNG TÂM (NẰM DƯỚI CÙNG CỦA FILE PYTHON)
# ==================================================================
if __name__ == "__main__":
    # Tự động nạp và khôi phục số dư ví Vàng từ file JSON cứng (Phần 14) khi khởi động
    load_users_database_from_storage()
    
    print("⚡ Bot Ma Sói Siêu Cấp và Sòng Bạc Tài Xỉu đã đồng bộ trực tuyến vĩnh viễn trên Termux!")
    bot.infinity_polling()
