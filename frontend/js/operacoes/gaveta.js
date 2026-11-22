// ==========================================================================
// OPERACOES/GAVETA.JS - Suprimento, Sangria, Leitura X e Autorização
// ==========================================================================
import { estadoPDV, formatarMoeda, getOperador, getTerminal } from "../state.js";
import { pdvAPI } from "../api.js";
import { pedirDadoModal } from "../ui/modal-universal.js";
import { focarEAN, imprimirLeituraXNaBobina } from "../ui/bobina.js";

export function toggleMenuAuxiliar(forcarEstado) {
  estadoPDV.menuAuxiliarAberto = typeof forcarEstado === "boolean"
    ? forcarEstado
    : !estadoPDV.menuAuxiliarAberto;
  document.getElementById("painel-menu-aux").classList.toggle("hidden", !estadoPDV.menuAuxiliarAberto);
}

export async function verificarPermissaoGerente() {
  const operador = getOperador();
  const grupo = (operador?.grupo_geral || "").trim().toUpperCase();
  if (["GERENTE", "ADMIN", "SUPORTE"].includes(grupo)) {
    return operador.usua_nome;
  }
  const senha = await pedirDadoModal({
    titulo: "AUTORIZAÇÃO DE SUPERVISOR / GERENTE",
    label: "Digite a senha de autorização:",
    tipo: "senha",
    dica: "Operação restrita ao nível Gerente ou Administrador."
  });
  return senha && senha.trim() !== "" ? "GERENTE_AUTORIZADO" : null;
}

export async function executarSuprimento() {
  toggleMenuAuxiliar(false);
  const autorizador = await verificarPermissaoGerente();
  if (!autorizador) return;

  const valStr = await pedirDadoModal({
    titulo: "SUPRIMENTO DE CAIXA [F1]",
    label: "Informe o valor do suprimento (R$):",
    valorInicial: "0,00",
    tipo: "moeda"
  });
  if (valStr === null) return;

  const valor = parseFloat(valStr.replace(/\./g, "").replace(",", "."));
  if (isNaN(valor) || valor <= 0) return alert("Valor inválido para suprimento!");

  try {
    const res = await pdvAPI.registrarSuprimento({
      terminal_id: getTerminal().codigo,
      operador: getOperador().usua_nome,
      gerente_autorizador: autorizador,
      valor
    });
    alert(`Suprimento de R$ ${formatarMoeda(valor)} registrado com sucesso! (ID: ${res.id})`);
  } catch (e) {
    alert("Falha no Suprimento: " + e.message);
  } finally {
    focarEAN();
  }
}

export async function executarSangria() {
  toggleMenuAuxiliar(false);
  const autorizador = await verificarPermissaoGerente();
  if (!autorizador) return;

  const valStr = await pedirDadoModal({
    titulo: "SANGRIA DE CAIXA [F2]",
    label: "Informe o valor da sangria (R$):",
    valorInicial: "0,00",
    tipo: "moeda"
  });
  if (valStr === null) return;

  const valor = parseFloat(valStr.replace(/\./g, "").replace(",", "."));
  if (isNaN(valor) || valor <= 0) return alert("Valor inválido para sangria!");

  try {
    const res = await pdvAPI.registrarSangria({
      terminal_id: getTerminal().codigo,
      operador: getOperador().usua_nome,
      gerente_autorizador: autorizador,
      valor
    });
    alert(`Sangria de R$ ${formatarMoeda(valor)} registrada com sucesso! (ID: ${res.id})`);
  } catch (e) {
    alert("Falha na Sangria: " + e.message);
  } finally {
    focarEAN();
  }
}

export async function emitirLeituraX() {
  toggleMenuAuxiliar(false);
  const terminal = getTerminal();
  try {
    const dados = await pdvAPI.emitirLeituraX(terminal.codigo, terminal.serie);
    imprimirLeituraXNaBobina(dados, getOperador().usua_nome, terminal.serie);
  } catch (e) {
    alert("Falha ao emitir Leitura X: " + e.message);
  } finally {
    focarEAN();
  }
}
