import pyodbc
import time
from selenium import webdriver
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Datos de conexión globales
CONN_STR = (
    'DRIVER={SQL Server};'
    'SERVER=10.52.108.12;'
    'DATABASE=Prepago;'
    'UID=migracion;'
    'PWD=commandcenter@'
)

def crear_driver():
    """Crea y configura una nueva instancia de Chrome."""
    chrome_options = Options()
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--disable-features=GCM')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # chrome_options.add_argument('--headless') # Opcional
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://sns.ift.org.mx:8081/sns-frontend/consulta-numeracion/numeracion-geografica.xhtml")
    return driver

def consultar_numero(numero, driver_idx, drivers_list):
    """Procesa un número y recupera el driver si falla."""
    driver = drivers_list[driver_idx]
    local_cnxn = None
    
    # 0. Verificar si el driver sigue vivo, si no, reiniciarlo
    try:
        _ = driver.current_url
    except Exception:
        print(f"[!] Driver {driver_idx} detectado como cerrado. Reiniciando...")
        try: driver.quit()
        except: pass
        driver = crear_driver()
        drivers_list[driver_idx] = driver

    try:
        local_cnxn = pyodbc.connect(CONN_STR)
        local_cursor = local_cnxn.cursor()
        wait = WebDriverWait(driver, 10)
        
        # 1. Esperar y encontrar el campo de texto
        try:
            national_number_input = wait.until(
                EC.element_to_be_clickable((By.ID, "FORM_myform:TXT_NationalNumber"))
            )
            national_number_input.clear()
            national_number_input.send_keys(numero)
        except Exception as e:
            print(f"Error al encontrar input para {numero}: {e}")
            driver.get("https://sns.ift.org.mx:8081/sns-frontend/consulta-numeracion/numeracion-geografica.xhtml")
            return

        # 2. Click en buscar
        try:
            time.sleep(1) 
            search_button = driver.find_element(By.XPATH, "//button[@id='FORM_myform:BTN_publicSearch']")
            search_button.click()
        except Exception as e:
            print(f"Error al buscar {numero}: {e}")
            driver.get("https://sns.ift.org.mx:8081/sns-frontend/consulta-numeracion/numeracion-geografica.xhtml")
            return 

        # 3. Extraer resultado
        proveedor = ""
        for _ in range(10):
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            proveedor_div = soup.find('div', string='Proveedor que atiende el número.')
            if proveedor_div:
                proveedor = proveedor_div.find_next_sibling('div').text.strip()
                break
            time.sleep(0.5)

        # 4. Actualizar DB
        if proveedor:
            print(f"Éxito Hilo {driver_idx}: {numero} -> {proveedor}")
            fecha_actualizacion = time.strftime("%Y-%m-%d %H:%M:%S")
            local_cursor.execute(
                "UPDATE Referidos SET Operador = ?, FechaOperador = ? WHERE numero = ? and FechaOperador IS NULL",
                (proveedor, fecha_actualizacion, numero)
            )
            local_cnxn.commit()
        else:
            print(f"Sin resultado: {numero}")

        # 5. Limpiar
        try:
            clear_button = driver.find_element(By.ID, "FORM_myform:LINK_CLEAR")
            clear_button.click()
            time.sleep(0.5)
        except:
            driver.get("https://sns.ift.org.mx:8081/sns-frontend/consulta-numeracion/numeracion-geografica.xhtml")

    except Exception as e:
        print(f"Error en consulta {numero}: {e}")
    finally:
        if local_cnxn: local_cnxn.close()

def procesar_lote(numeros, driver_idx, drivers_list):
    for numero in numeros:
        consultar_numero(numero, driver_idx, drivers_list)

if __name__ == '__main__':
    max_sessions = 5
    drivers = []
    
    print(f"Iniciando {max_sessions} navegadores...")
    for i in range(max_sessions):
        drivers.append(crear_driver())

    print("\n--- BARRIDO CON AUTORRECUPERACIÓN ACTIVADO ---")

    main_cnxn = None
    while True:
        try:
            # Reconexión SQL si se pierde
            if main_cnxn is None:
                main_cnxn = pyodbc.connect(CONN_STR)
                main_cursor = main_cnxn.cursor()

            query = """
                SELECT TOP 500 numero
                FROM [Prepago].[dbo].[Referidos]
                WHERE FechaOperador IS NULL and convert(date,fechainserto) >=convert(date,getdate()-7)
                GROUP BY numero
                ORDER BY  MIN(CASE WHEN empleado = 'Mia' THEN 0 ELSE 1 END), NEWID()
            """
            main_cursor.execute(query)
            rows = main_cursor.fetchall()
            
            if not rows:
                print("Tabla vacía. Esperando...")
                time.sleep(5)
                continue

            numeros_pendientes = [row.numero for row in rows]
            num_sublist_size = (len(numeros_pendientes) + max_sessions - 1) // max_sessions
            lotes = [numeros_pendientes[i:i+num_sublist_size] for i in range(0, len(numeros_pendientes), num_sublist_size)]

            with ThreadPoolExecutor(max_workers=max_sessions) as executor:
                # Pasamos el índice y la lista de drivers para que el hilo pueda actualizarla si falla
                futures = [executor.submit(procesar_lote, lote, i, drivers) for i, lote in enumerate(lotes)]
                for future in futures:
                    future.result()
            
            print(f"Lote finalizado. Consultando...")

        except (pyodbc.Error, Exception) as e:
            print(f"[!] Error en bucle principal o SQL: {e}. Reintentando en 5s...")
            main_cnxn = None # Forzar reconexión en el siguiente ciclo
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nDeteniendo...")
            break

    # Limpieza final
    for d in drivers:
        try: d.quit()
        except: pass