from backend.suporte.gerador_xml import gerar_xml_nfe

xml = gerar_xml_nfe('COLE-AQUI-O-UUID-DA-NOTA', db_path='pdv.db')
print(xml[:300]) # Exibe o início do XML gerado
