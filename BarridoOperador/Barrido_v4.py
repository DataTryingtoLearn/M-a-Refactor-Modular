
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pyodbc
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from datetime import datetime

# --- CONFIGURACIÓN ---
NUM_HILOS = 4
ACTUALIZAR_BD = True  # True = actualiza, False = solo visualiza
# Si tienes una ruta personalizada de Chrome, úsala en executable_path, 
# si no, 'channel="chrome"' es lo ideal.
CHROME_CHANNEL = "chrome" 

def delay_humano(min_seg=1, max_seg=4):
    tiempo = random.uniform(min_seg, max_seg)
    time.sleep(tiempo)
    return tiempo

def delay_entre_consultas():
    if random.random() < 0.3:
        tiempo = random.uniform(5, 10)
        print(f"    💤 Descanso de {tiempo:.1f} segundos...")
        time.sleep(tiempo)

def movimiento_mouse_aleatorio(page):
    x = random.randint(100, 800)
    y = random.randint(100, 600)
    page.mouse.move(x, y, steps=random.randint(1, 2))
    delay_humano(0.1, 0.3)

def consultar_lote(numeros_lote, resultados_compartidos, lock, worker_id):
    """
    Worker con su propia conexión a BD que actualiza en tiempo real usando Google Chrome
    """
    try:
        local_cnxn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=10.52.108.12;'
            'DATABASE=Prepago;'
            'UID=E015379;'
            'PWD=Quetalteva22#;'
        )
        local_cursor = local_cnxn.cursor()
        print(f"[Worker {worker_id}] ✅ Conexión a BD establecida")
    except Exception as e:
        print(f"[Worker {worker_id}] ❌ Error conectando a BD: {e}")
        return

    with sync_playwright() as p:
        # INTEGRACIÓN DE CHROME OFICIAL
        try:
            browser = p.chromium.launch(
                channel=CHROME_CHANNEL, # <--- Aquí indicamos que use Chrome y no Chromium
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-automation',
                    '--start-maximized'
                ]
            )
        except Exception as e:
            print(f"[Worker {worker_id}] ❌ No se encontró Google Chrome instalado: {e}")
            return
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        print(f"[Worker {worker_id}] 🚜 Navegador Chrome iniciado...")
        
        try:
            page.goto("https://sns.ift.org.mx:8081/sns-frontend/consulta-numeracion/numeracion-geografica.xhtml", 
                     wait_until="networkidle")
        except Exception as e:
            print(f"[Worker {worker_id}] ❌ Error al cargar página inicial: {e}")
            browser.close()
            return

        delay_humano(1, 3)
                
        for i, numero in enumerate(numeros_lote):
            try:
                print(f"[Worker {worker_id}] [{i+1}/{len(numeros_lote)}] Consultando {numero}...")
                
                movimiento_mouse_aleatorio(page)
                
                # Localizar input
                input_selector = "input[name='FORM_myform:TXT_NationalNumber']"
                page.wait_for_selector(input_selector, timeout=10000)
                
                # Limpiar y escribir (SIN await, es sync_api)
                page.locator(input_selector).clear()
                delay_humano(0.2, 0.4)
                
                for digito in numero:
                    page.keyboard.type(digito)
                    time.sleep(random.uniform(0.05, 0.1))
                
                page.keyboard.press("Tab")
                delay_humano(0.3, 0.6)
                
                # Buscar botón y click
                btn_buscar = "#FORM_myform\\:BTN_publicSearch"
                page.wait_for_selector(f"{btn_buscar}:not([disabled])", timeout=5000)
                page.click(btn_buscar)
                
                # Esperar a que el bloqueo visual desaparezca
                try:
                    page.wait_for_selector(".ui-blockui-content", state="hidden", timeout=12000)
                except:
                    pass
                
                # Extraer proveedor
                page.wait_for_selector("text=Proveedor que atiende el número", timeout=10000)
                
                proveedor = "No encontrado / No asignado"
                celdas = page.locator(".ui-panelgrid-cell").all()
                
                for idx, celda in enumerate(celdas):
                    content = celda.text_content()
                    if content and "Proveedor que atiende el número" in content:
                        proveedor = celdas[idx + 1].text_content().strip()
                        break
                
                print(f"[Worker {worker_id}] 🏢 {numero} -> {proveedor}")
                
                with lock:
                    resultados_compartidos[numero] = proveedor
                
                # ACTUALIZACIÓN EN BD
                if ACTUALIZAR_BD and proveedor not in ["Error", "No encontrado / No asignado"]:
                    try:
                        ahora = datetime.now()
                        local_cursor.execute(
                            "UPDATE Referidos SET Operador = ?, FechaOperador = ? WHERE numero = ? AND FechaOperador IS NULL",
                            (proveedor, ahora, numero)
                        )
                        local_cnxn.commit()
                        print(f"[Worker {worker_id}] 💾 BD Actualizada")
                    except Exception as e:
                        print(f"[Worker {worker_id}] ❌ Error BD: {e}")
                
                # Limpiar formulario para la siguiente consulta
                page.locator("button", has_text="Limpiar").click()
                delay_humano(1, 2)
                
                if (i + 1) % 5 == 0:
                    delay_entre_consultas()

            except Exception as e:
                print(f"[Worker {worker_id}] ❌ Error en ciclo con {numero}: {e}")
                with lock:
                    resultados_compartidos[numero] = "Error"
                # Recargar página si hay errores críticos
                page.reload()
                delay_humano(2, 4)
        
        browser.close()
        local_cnxn.close()

def consulta_masiva_paralela():
    resultados = {}
    lock = threading.Lock()
    
    # Obtener números iniciales
    try:
        cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.52.108.12;DATABASE=Prepago;UID=E015379;PWD=Quetalteva22#;')
        cursor = cnxn.cursor()
        query = """
            select distinct numero FROM [Prepago].[dbo].[Referidos]
            where empleado='mia' and fechaoperador is null
            and fechainserto >= getdate()-7
        """
        cursor.execute(query)
        lista_numeros = [str(row[0]) for row in cursor.fetchall()]
        cnxn.close()
        
        if not lista_numeros:
            print("[*] 📭 No hay números pendientes.")
            return {}

        print(f"[*] 📊 Pendientes: {len(lista_numeros)} | Workers: {NUM_HILOS}")
        random.shuffle(lista_numeros)
        
        lotes = [lista_numeros[i::NUM_HILOS] for i in range(NUM_HILOS)]
        
        with ThreadPoolExecutor(max_workers=NUM_HILOS) as executor:
            futures = [executor.submit(consultar_lote, lote, resultados, lock, i) for i, lote in enumerate(lotes)]
            for future in as_completed(futures):
                future.result()
                
    except Exception as e:
        print(f"[*] ❌ Error General: {e}")
    
    return resultados

if __name__ == "__main__":

    consulta_masiva_paralela()
    