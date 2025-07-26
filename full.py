import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json

# ====== КАСТОМНЫЙ CSS ======
st.markdown(
    """
    <style>
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div > div,
    .stNumberInput input {
        min-width: 500px !important;
        max-width: 700px !important;
    }
    .block-container {
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Google Sheets Setup ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not GOOGLE_SERVICE_ACCOUNT_JSON:
    st.error("Google Service Account JSON не найден в переменных окружения!")
    st.stop()
service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

# ==== HELPERS ====
def get_next_id():
    sheet = client.open("База клиентов").worksheet("База клиентов")
    id_list = sheet.col_values(1)[1:]
    id_list = [int(x) for x in id_list if x.isdigit()]
    return max(id_list) + 1 if id_list else 1

def get_next_order_id():
    sheet = client.open("База клиентов").worksheet("База заказов")
    values = sheet.col_values(1)[1:]
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

@st.cache_data
def load_orders():
    sheet = client.open("База клиентов").worksheet("База заказов")
    return sheet.get_all_records()

def append_client(values):
    sheet = client.open("База клиентов").worksheet("База клиентов")
    sheet.append_row(values)

def update_client_in_sheet(client_id, values):
    sheet = client.open("База клиентов").worksheet("База клиентов")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if str(row.get("ID")) == str(client_id):
            sheet.update(f"A{i+2}:J{i+2}", [values])
            break

def save_order_to_sheet(order_rows, client_info, payment_info, order_id):
    sheet = client.open("База клиентов").worksheet("База заказов")
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

def update_order_in_sheet(order_id, updates: dict):
    sheet = client.open("База клиентов").worksheet("База заказов")
    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if str(row.get("ID заказа")) == str(order_id):
            row_number = i + 2
            if "Сумма (грн)" in updates:
                sheet.update(f"W{row_number}", [[updates["Сумма (грн)"]]])
            if "Тип оплати" in updates:
                sheet.update(f"L{row_number}", [[updates["Тип оплати"]]])
            if "Дата заказа" in updates:
                sheet.update(f"X{row_number}", [[updates["Дата заказа"]]])
            break
    load_orders.clear()  # Сброс кэша

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
                st.session_state.page = "orders"
                st.session_state.found_client = False
                st.rerun()
        with col3:
            if st.button("✏️ Змінити картку клієнта"):
                st.session_state.found_client = False
                go_to("edit_client")
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
        load_clients.clear()
        st.success(f"Клієнта додано з ID: {actual_id}")
        st.session_state.client_id = actual_id
        st.session_state.client_name = name
        st.session_state.just_added_client = True

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

# ==== PAGE 3: Список заказов клиента ====
def page_orders():
    st.markdown("<h2 style='text-align: center;'>Всі замовлення клієнта</h2>", unsafe_allow_html=True)
    client_id = st.session_state.get("client_id")
    orders = load_orders()
    # если зашли с found_client == False
    if not client_id:
        client_id = st.session_state.get("client_id") or st.session_state.get("selected_client_id")
    client_orders = [o for o in orders if str(o.get("ID клиента")) == str(client_id)]
    # --- Берём только уникальные заказы по ID заказа ---
    unique_orders = {}
    for o in client_orders:
        order_id = o.get("ID заказа")
        if order_id not in unique_orders:
            unique_orders[order_id] = o
    unique_orders_list = sorted(unique_orders.values(), key=lambda x: x.get('Дата заказа', ''), reverse=True)
    if not unique_orders_list:
        st.info("У клієнта ще немає замовлень.")
    else:
        order_display = [
            f"ID: {o['ID заказа']} | {o.get('Дата заказа','')} | {o.get('Сумма (грн)','0')} грн | {o.get('Тип оплати','')}"
            for o in unique_orders_list
        ]
        selected = st.selectbox("Виберіть замовлення:", order_display, key="select_order")
        if st.button("Відкрити замовлення"):
            order_id = selected.split('|')[0].replace("ID:", "").strip()
            st.session_state.edit_order_id = order_id
            st.session_state.page = "edit_order"
            st.rerun()
    if st.button("⬅️ Назад до клієнта"):
        st.session_state.page = "check"
        st.rerun()
    st.stop()

# ==== PAGE 4: Карточка заказа (редактирование) ====
def page_edit_order():
    orders = load_orders()
    order_id = st.session_state.get("edit_order_id")
    order = next((o for o in orders if str(o.get("ID заказа")) == str(order_id)), None)
    if not order:
        st.warning("Замовлення не знайдено.")
        if st.button("⬅️ До замовлень"):
            st.session_state.page = "orders"
            st.rerun()
        st.stop()
    st.markdown(f"### Замовлення ID: {order['ID заказа']}")
    new_sum = st.text_input("Сума (грн)", value=str(order.get("Сумма (грн)", "")), key="edit_order_sum")
    new_pay = st.selectbox("Тип оплати", ["Без оплати", "Передплата", "Повна оплата"], 
        index=["Без оплати", "Передплата", "Повна оплата"].index(order.get("Тип оплати", "Без оплати")), key="edit_order_pay")
    new_date = st.text_input("Дата замовлення", value=order.get("Дата заказа", ""), key="edit_order_date")
    if st.button("Зберегти зміни"):
        update_order_in_sheet(order["ID заказа"], {
            "Сумма (грн)": new_sum,
            "Тип оплати": new_pay,
            "Дата заказа": new_date
        })
        st.success("Зміни збережено!")
        st.stop()
    if st.button("⬅️ Назад до всіх замовлень"):
        st.session_state.page = "orders"
        st.rerun()
    st.stop()

# ==== PAGE 5: Редактирование клиента ====
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
            "",
            name,
            surname,
            city,
            np,
            delivery,
            comment,
            1
        ]
        update_client_in_sheet(client_id, values)
        load_clients.clear()
        st.success("Картка клієнта успішно оновлена!")
        st.session_state.found_client = False
        go_to("check")
    if st.button("⬅️ До пошуку"):
        go_to("check")

# ==== PAGE 6: Создание заказа ====
# (Тут оставь свою page_order(), если она у тебя была. Она не изменяется этим обновлением.)

# ==== Роутинг ====
if st.session_state.page == "check":
    page_check()
elif st.session_state.page == "create":
    page_create()
elif st.session_state.page == "order":
    page_order()
elif st.session_state.page == "edit_client":
    page_edit_client()
elif st.session_state.page == "orders":
    page_orders()
elif st.session_state.page == "edit_order":
    page_edit_order()
