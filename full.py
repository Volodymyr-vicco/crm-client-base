import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Google Sheets Setup ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# ==== HELPERS ====
def get_next_id():
    sheet = client.open("База клиентов").worksheet("База клиентов")
    id_list = sheet.col_values(1)[1:]
    id_list = [int(x) for x in id_list if x.isdigit()]
    return max(id_list) + 1 if id_list else 1

def get_next_order_id():
    sheet = client.open("База клиентов").worksheet("База заказов")
    values = sheet.col_values(1)[1:]  # Пропускаем шапку
    id_numbers = [int(x) for x in values if x.isdigit()]
    return max(id_numbers) + 1 if id_numbers else 1

@st.cache_data
def load_clients():
    sheet = client.open("База клиентов").worksheet("База клиентов")
    return sheet.get_all_records()

@st.cache_data
def load_price():
    sheet = client.open("База клиентов").worksheet("Прайс")
    return sheet.get_all_records()

@st.cache_data
def load_sizes():
    sheet = client.open("База клиентов").worksheet("Размерный ряд")
    return sheet.get_all_records()

@st.cache_data
def load_colors():
    sheet = client.open("База клиентов").worksheet("Цветовая линейка")
    return sheet.get_all_records()

def append_client(values):
    sheet = client.open("База клиентов").worksheet("База клиентов")
    sheet.append_row(values)

def update_client_in_sheet(client_id, values):
    sheet = client.open("База клиентов").worksheet("База клиентов")
    records = sheet.get_all_records()
    # Найти строку по ID
    for i, row in enumerate(records):
        if str(row.get("ID")) == str(client_id):
            # i+2 потому что get_all_records не возвращает шапку, а Google Sheets начинается с 1
            sheet.update(f"A{i+2}:J{i+2}", [values])
            break

def save_order_to_sheet(order_rows, client_info, payment_info, order_id):
    sheet = client.open("База клиентов").worksheet("База заказов")
    # Проверка на шапку (если таблица пуста — добавить!)
    if not sheet.get_all_values():
        sheet.append_row([
            "ID заказа",
            "ID клиента", "Имя", "Фамилия", "Телефон", "Город", "НП", "Доставка", "Комментарий",
            "Валюта", "Тип оплаты", "Сумма предоплаты", "До сплати",
            "Название модели", "Цвет", "Размер", "Ручной размер", "К-во в ростовке", "К-во ростовок",
            "Общ. кол-во", "Цена/шт", "Скидка", "Сумма (грн)", "Дата заказа"
        ])
    for row in order_rows:
        manual_size = ""
        size_value = row.get("size", "")
        if "ввести" in str(row.get("size", "")).lower() or "ручн" in str(row.get("size", "")).lower():
            manual_size = row.get("size", "")
            size_value = ""
        sheet.append_row([
            order_id,
            client_info["ID"],
            client_info["Ім'я"],
            client_info["Прізвище"],
            client_info["Номер телефону"],
            client_info["Місто"],
            client_info["НП"],
            client_info["Доставка"],
            client_info["Коментар"],
            payment_info["Валюта"],
            payment_info["Тип оплати"],
            payment_info["Сумма предоплаты"] if payment_info["Тип оплати"] == "Передплата" else 0,
            payment_info["До сплати"],
            row.get("model", ""),
            row.get("color", ""),
            size_value,
            manual_size,
            row.get("v_rostovke", ""),
            row.get("qty_rostovok", ""),
            row.get("total_qty", ""),
            row.get("price", ""),
            row.get("discount", ""),
            row.get("total_sum", ""),
            datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        ])

# ==== Навигация ====
if "page" not in st.session_state:
    st.session_state.page = "check"

def go_to(page):
    st.session_state.page = page
    st.rerun()

# ==== PAGE 1: Поиск/проверка клиента ====
def page_check():
    st.markdown("<h2 style='text-align: center;'>Перевірка номера клієнта</h2>", unsafe_allow_html=True)
    records = load_clients()
    client_dict = {}
    for row in records:
        phone = str(row.get("Номер", "")).strip()
        if phone and phone[0] != '0' and len(phone) == 9:
            phone = '0' + phone
        client_dict[phone] = {
            "id": row.get("ID"),
            "name": row.get("Имя", ""),
        }
    user_input = st.text_input("Введіть номер телефону (наприклад: 068):").strip()
    matches = sorted([num for num in client_dict if num.startswith(user_input)]) if user_input else []
    selected = st.selectbox("Найдені номери:", matches) if matches else None

    if st.button("Next ➜"):
        if selected and selected in client_dict:
            st.session_state.client_id = client_dict[selected]["id"]
            st.session_state.client_name = client_dict[selected]["name"]
            st.session_state.client_phone = selected
            st.session_state.found_client = True
            st.rerun()
        else:
            st.session_state.proposed_phone = user_input
            go_to("create")

    if st.session_state.get("found_client", False):
        st.markdown(
            f"""
            <div style="background-color:#eafbea; border-radius:8px; padding:16px;">
            ✅ <b>Знайдено клієнта:</b><br>
            <span style="font-size:1.1em;">
              👤 <b>{st.session_state['client_name']}</b>
              <span style="color:#673ab7;"><b>ID:</b> {st.session_state['client_id']}</span>
              <span style="color:#222;">📞 {st.session_state['client_phone']}</span>
            </span>
            </div>
            """,
            unsafe_allow_html=True
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🛒 Створити новий заказ"):
                st.session_state.found_client = False
                go_to("order")
        with col2:
            if st.button("🔎 Подивитися всі замовлення"):
                st.info("Поки функція не реалізована")
        with col3:
            if st.button("✏️ Змінити картку клієнта"):
                st.session_state.found_client = False
                go_to("edit_client")  # <--- добавляем переход на страницу редактирования!
        with col4:
            if st.button("⬅️ До пошуку"):
                st.session_state.found_client = False
                go_to("check")
        st.stop()

# ==== PAGE 2: Создание нового клиента ====
def page_create():
    st.markdown("<h2 style='text-align: center;'>Створення нового клієнта</h2>", unsafe_allow_html=True)
    next_id = get_next_id()
    st.info(f"ID нового клієнта: {next_id}")
    with st.form("new_client_form"):
        phone = st.text_input("Номер телефону", value=st.session_state.get("proposed_phone", ""))
        name = st.text_input("Ім'я")
        surname = st.text_input("Прізвище")
        city = st.text_input("Місто")
        delivery = st.text_input("Доставка")
        np = st.text_input("НП")
        comment = st.text_input("Коментар")
        submitted = st.form_submit_button("Зберегти клієнта")
    if submitted:
        actual_id = get_next_id()
        values = [
            actual_id,
            phone,
            "",
            name,
            surname,
            city,
            np,
            delivery,
            comment,
            1
        ]
        append_client(values)
        load_clients.clear()  # <--- Сброс кэша после добавления!
        st.success(f"Клієнта додано з ID: {actual_id}")
        # Сохраняем id и имя клиента
        st.session_state.client_id = actual_id
        st.session_state.client_name = name
        st.session_state.just_added_client = True

    # После успешного добавления показываем только 2 кнопки
    if st.session_state.get("just_added_client", False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🛒 Створити новий заказ для цього клієнта"):
                st.session_state.just_added_client = False
                go_to("order")
        with col2:
            if st.button("⬅️ До пошуку"):
                st.session_state.just_added_client = False
                go_to("check")
        st.stop()

    if st.button("⬅️ Назад до перевірки"):
        go_to("check")

# ==== PAGE 3: Создание заказа ====
def page_order():
    price_data = load_price()
    size_data = load_sizes()
    color_data = load_colors()
    clients = load_clients()
    client_info = next((row for row in clients if str(row.get("ID")) == str(st.session_state.get("client_id"))), {})

    if not client_info:
        st.warning("Клієнта не знайдено. Поверніться до вибору клієнта.")
        if st.button("⬅️ Назад"):
            go_to("check")
        st.stop()

    st.header("Створення замовлення")
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Ім'я", value=client_info.get("Имя", ""))
    with col2:
        surname = st.text_input("Прізвище", value=client_info.get("Фамилия", ""))
    with col3:
        phone = st.text_input("Номер телефону", value=client_info.get("Номер", ""))

    col4, col5, col6 = st.columns(3)
    with col4:
        city = st.text_input("Місто", value=client_info.get("Город", ""))
    with col5:
        np = st.text_input("НП (Нова Пошта)", value=client_info.get("НП", ""))
    with col6:
        delivery = st.text_input("Доставка", value=client_info.get("Доставка", ""))

    comment = st.text_input("Коментар (Ім’я отримувача)", value=client_info.get("Комент", ""))

    st.markdown("---")
    currency = st.selectbox("Валюта", ["ГРН", "USD"])
    pay_type = st.selectbox("Тип оплати", ["Без оплати", "Передплата", "Повна оплата"])
    prepay_amount = 0
    if pay_type == "Передплата":
        prepay_amount = st.number_input("Сума предоплати", min_value=0.0, step=1.0)

    st.markdown("---")
    models = []
    seen = set()
    for row in price_data:
        m = row.get("Модель")
        if m and m not in seen:
            models.append(m)
            seen.add(m)

    if "order_rows" not in st.session_state:
        st.session_state.order_rows = []

    st.subheader("Додайте товар")
    def add_row():
        size_display = ""
        v_rostovke = 1
        for sd in size_data:
            if sd["Модель"] == models[0]:
                size_display = str(sd.get("Размеры ростовки", "")).strip()
                try:
                    v_rostovke = int(sd.get("В ростовке", 1))
                except:
                    v_rostovke = 1
                break
        st.session_state.order_rows.append({
            "model": models[0],
            "color": "",
            "size": size_display,
            "v_rostovke": v_rostovke,
            "qty_rostovok": 1,
            "total_qty": v_rostovke,
            "price": 0.0,
            "discount": 0.0,
            "total_sum": 0.0
        })

    if st.button("➕ Додати товар"):
        add_row()

    for idx, row in enumerate(st.session_state.order_rows):
        st.markdown(f"**Товар #{idx+1}**")
        cols = st.columns(6)
        row["model"] = cols[0].selectbox(
            "Модель", models, index=models.index(row["model"]) if row["model"] in models else 0, key=f"model_{idx}"
        )
        color_choices = [r["Цвет"] for r in color_data if r["Модель"] == row["model"]]
        row["color"] = cols[1].selectbox(
            "Колір", color_choices + ["Ввести свій..."], index=color_choices.index(row["color"]) if row["color"] in color_choices else 0, key=f"color_{idx}"
        )
        if row["color"] == "Ввести свій...":
            row["color"] = cols[1].text_input("Введіть свій колір:", key=f"custom_color_{idx}")

        size_display = ""
        v_rostovke_db = 1
        for sd in size_data:
            if sd["Модель"] == row["model"]:
                size_display = str(sd.get("Размеры ростовки", "")).strip()
                try:
                    v_rostovke_db = int(sd.get("В ростовке", 1))
                except:
                    v_rostovke_db = 1
                break
        sizes_display = [size_display] if size_display else []
        current_idx = sizes_display.index(row["size"]) if row["size"] in sizes_display else len(sizes_display)
        row["size"] = cols[2].selectbox(
            "Розмір", sizes_display + ["Ввести вручну..."], index=current_idx, key=f"size_{idx}"
        )

        if row["size"] == "Ввести вручну...":
            row["size"] = cols[2].text_input("Введіть розмір:", key=f"custom_size_{idx}")
            row["v_rostovke"] = cols[3].number_input("Кількість у рост.", value=row.get("v_rostovke", 1), min_value=1, step=1, key=f"v_rost_{idx}")
        else:
            row["v_rostovke"] = cols[3].number_input("Кількість у рост.", value=v_rostovke_db, min_value=1, step=1, key=f"v_rost_{idx}", disabled=True)

        row["qty_rostovok"] = cols[4].number_input("Кількість ростовок", value=row.get("qty_rostovok", 1), min_value=1, step=1, key=f"qty_rost_{idx}")
        row["total_qty"] = row["v_rostovke"] * row["qty_rostovok"]
        cols[5].number_input("Загальна Кількість", value=row["total_qty"], min_value=1, step=1, key=f"total_qty_{idx}", disabled=True)

        price_col, disc_col, sum_col = st.columns([2, 2, 3])
        price = None
        for pd in price_data:
            if pd["Модель"] == row["model"]:
                price = float(pd.get("Ц $/шт", 0)) if currency == "USD" else float(pd.get("Ц ГРН/шт", 0))
                break
        if price is not None:
            row["price"] = price_col.number_input("Ціна/шт", value=price, min_value=0.0, step=0.01, key=f"price_{idx}", disabled=True)
        else:
            row["price"] = price_col.number_input("Ціна/шт", min_value=0.0, step=0.01, key=f"price_{idx}")

        row["discount"] = disc_col.number_input("Знижка", value=row.get("discount", 0.0), min_value=0.0, step=1.0, key=f"discount_{idx}")
        row["total_sum"] = row["total_qty"] * row["price"] - row["discount"]
        sum_col.number_input("Загалом, грн", value=row["total_sum"], key=f"total_sum_{idx}", disabled=True)

        if st.button(f"Видалити товар {idx+1}"):
            st.session_state.order_rows.pop(idx)
            st.rerun()

    st.markdown("---")
    if st.session_state.order_rows:
        order_total = sum(row["total_sum"] for row in st.session_state.order_rows)
    else:
        order_total = 0

    if pay_type == "Без оплати":
        to_pay = order_total
    elif pay_type == "Передплата":
        to_pay = order_total - prepay_amount
    else:
        to_pay = 0

    st.info(f"**До сплати:** {to_pay:.2f} {currency}")

    if st.button("Зберегти замовлення"):
        order_id = get_next_order_id()
        save_order_to_sheet(
            st.session_state.order_rows,
            {
                "ID": st.session_state.get("client_id"),
                "Ім'я": name,
                "Прізвище": surname,
                "Номер телефону": phone,
                "Місто": city,
                "НП": np,
                "Доставка": delivery,
                "Коментар": comment
            },
            {
                "Валюта": currency,
                "Тип оплати": pay_type,
                "Сумма предоплаты": prepay_amount,
                "До сплати": to_pay
            },
            order_id
        )
        st.session_state.order_rows = []
        st.session_state.order_saved = order_id  # Ставим флаг!
        st.rerun()  # Перезапускаем страницу

    if st.session_state.get("order_saved"):
        order_id = st.session_state.order_saved
        st.success(f"Замовлення збережено! ID замовлення: {order_id}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Повернутись до пошуку клієнтів"):
                st.session_state.order_saved = None  # Сброс флага!
                go_to("check")
        with col2:
            if st.button("🛒 Створити ще одне замовлення для цього клієнта"):
                st.session_state.order_saved = None  # Сброс флага!
                go_to("order")
        st.stop()

# ==== PAGE 4: Редактирование клиента ====
def page_edit_client():
    clients = load_clients()
    client_id = st.session_state.get("client_id")
    client = next((row for row in clients if str(row.get("ID")) == str(client_id)), {})
    if not client:
        st.warning("Клієнта не знайдено.")
        if st.button("⬅️ До пошуку"):
            go_to("check")
        st.stop()
    st.markdown("<h2 style='text-align: center;'>Редагування картки клієнта</h2>", unsafe_allow_html=True)
    with st.form("edit_client_form"):
        phone = st.text_input("Номер телефону", value=client.get("Номер", ""))
        name = st.text_input("Ім'я", value=client.get("Имя", ""))
        surname = st.text_input("Прізвище", value=client.get("Фамилия", ""))
        city = st.text_input("Місто", value=client.get("Город", ""))
        np = st.text_input("НП", value=client.get("НП", ""))
        delivery = st.text_input("Доставка", value=client.get("Доставка", ""))
        comment = st.text_input("Коментар", value=client.get("Комент", ""))
        submitted = st.form_submit_button("Зберегти зміни")
    if submitted:
        values = [
            client_id,
            phone,
            "",  # Здесь можно добавить email или оставить пустым
            name,
            surname,
            city,
            np,
            delivery,
            comment,
            1
        ]
        update_client_in_sheet(client_id, values)
        load_clients.clear()  # Сбросить кэш после редактирования!
        st.success("Картка клієнта успішно оновлена!")
        st.session_state.found_client = False
        go_to("check")
    if st.button("⬅️ До пошуку"):
        go_to("check")

# ==== Роутинг ====
if st.session_state.page == "check":
    page_check()
elif st.session_state.page == "create":
    page_create()
elif st.session_state.page == "order":
    page_order()
elif st.session_state.page == "edit_client":
    page_edit_client()
