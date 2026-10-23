# -*- coding: utf-8 -*-
import os
import sys
import base64
from pyrevit import forms
from System.Diagnostics import Process, ProcessStartInfo

ICON_B64 = "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"

ICON_DARK_B64 = "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"


def _garantir_icones():
    """Gera os icones caso ainda nao existam na pasta."""
    pasta_btn = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(pasta_btn, "icon.png")
    icon_dark_path = os.path.join(pasta_btn, "icon.dark.png")

    try:
        if not os.path.exists(icon_path):
            with open(icon_path, "wb") as f:
                f.write(base64.b64decode(ICON_B64))
        if not os.path.exists(icon_dark_path):
            with open(icon_dark_path, "wb") as f:
                f.write(base64.b64decode(ICON_DARK_B64))
    except Exception:
        pass


def encontrar_raiz_git():
    """Localiza a pasta raiz contendo o .git navegando para cima."""
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return None


def encontrar_executavel_git():
    """Localiza o git.exe na maquina."""
    candidatos = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        "git.exe",
        "git"
    ]
    for c in candidatos:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            return c
    return "git"


def executar_git_pull(git_exe, repo_dir):
    """Executa o git pull de forma silenciosa e captura a saida."""
    psi = ProcessStartInfo()
    psi.FileName = git_exe
    psi.Arguments = "pull"
    psi.WorkingDirectory = repo_dir
    psi.UseShellExecute = False
    psi.RedirectStandardOutput = True
    psi.RedirectStandardError = True
    psi.CreateNoWindow = True

    proc = Process.Start(psi)
    saida = proc.StandardOutput.ReadToEnd()
    erro = proc.StandardError.ReadToEnd()
    proc.WaitForExit()
    return proc.ExitCode, saida, erro


def main():
    _garantir_icones()

    repo_dir = encontrar_raiz_git()
    if not repo_dir:
        forms.alert(
            u"A pasta da extensão não possui um repositório Git (.git) configurado.\n\n"
            u"Verifique se o ELE-Tools foi instalado via Git.",
            title=u"ELE-Tools - Git não encontrado"
        )
        return

    git_exe = encontrar_executavel_git()

    try:
        codigo, saida, erro = executar_git_pull(git_exe, repo_dir)
    except Exception as ex:
        forms.alert(
            u"Erro ao tentar executar o Git:\n{}".format(str(ex)),
            title=u"Erro ao Atualizar"
        )
        return

    texto_saida = (saida or u"").strip()
    texto_erro = (erro or u"").strip()

    if codigo == 0:
        if "Already up to date" in texto_saida or u"Já está atualizado" in texto_saida:
            forms.alert(
                u"O ELE-Tools já está sincronizado com a versão mais recente do GitHub!\n\nNenhuma nova alteração encontrada.",
                title=u"ELE-Tools Atualizado"
            )
        else:
            forms.alert(
                u"ELE-Tools atualizado com sucesso a partir do GitHub!\n\n"
                u"Detalhes:\n{}\n\n"
                u"O pyRevit será recarregado agora para ativar as atualizações.".format(texto_saida),
                title=u"Atualização Concluída"
            )
            # Recarrega o pyRevit automaticamente
            try:
                from pyrevit.loader import sessionmgr
                sessionmgr.reload_pyrevit()
            except Exception:
                forms.alert(u"Por favor, clique em 'Reload' na aba do pyRevit para aplicar.", title=u"Aviso")
    else:
        mensagem_erro = texto_erro or texto_saida or u"Código de saída: {}".format(codigo)
        forms.alert(
            u"Não foi possível concluir o update pelo Git:\n\n{}".format(mensagem_erro),
            title=u"Falha ao Atualizar ELE-Tools"
        )


if __name__ == "__main__":
    main()
