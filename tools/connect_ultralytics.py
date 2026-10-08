"""User-controlled, masked local dialog for read-only Platform access.

The credential is never written to disk, shell history or a subprocess argument.
Only a restricted access report is persisted; no training/import is started.
"""
import json
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog, messagebox

from ultralytics_tcc import Platform, access_report

OWNER = 'felipe-souza-nascimento'
REPORT = Path(__file__).resolve().parents[1]/'.local'/'ultralytics-access.json'


def check_and_save(key, report_path=REPORT):
    client = Platform(key=key.strip())
    try:
        report = access_report(client, OWNER)
    finally:
        # No persistent credential store; the client is only used for this check.
        client.key = ''
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    root = tk.Tk()
    root.withdraw()
    key = None
    try:
        key = simpledialog.askstring(
            'Edge Security - Conectar Ultralytics',
            'Na pagina API Keys da Ultralytics, copie a primeira chave (ul_...).\n'
            'Cole aqui. Os caracteres ficam ocultos e a chave nao sera salva.\n\n'
            'Este passo verifica acesso: nao inicia treino nem cobranca.\n'
            'Recomendamos substituir depois a chave exposta no chat.',
            show='*', parent=root)
        if not key:
            return
        check_and_save(key)
        key = None
        messagebox.showinfo('Ultralytics - Acesso verificado',
                            'Acesso de leitura verificado!\n'
                            'O resultado sem credenciais foi salvo localmente.\n'
                            'Nenhum treino ou importacao foi iniciado.\n'
                            'A chave nao fica disponivel para futuras execucoes.', parent=root)
    except (ValueError, OSError, KeyError):
        messagebox.showerror('Nao foi possivel verificar o acesso',
                             'Confira se copiou a chave completa que comeca com ul_.\n'
                             'Uma chave sk-proj- e da OpenAI e nao serve aqui.\n'
                             'Confira tambem a conexao e se a chave esta ativa.\n'
                             'Nenhum treino ou importacao foi iniciado.', parent=root)
    finally:
        key = None
        root.destroy()


if __name__ == '__main__':
    main()
