// ==========================================================================
// API.JS - Único arquivo que faz chamadas fetch() ao backend Python
// ==========================================================================

function getBaseUrl() {
  return typeof API_URL !== "undefined" ? API_URL : "http://localhost:8000/api/v1";
}

async function request(endpoint, options = {}) {
  const resp = await fetch(`${getBaseUrl()}${endpoint}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || "Erro na comunicação com o servidor.");
  }
  return data;
}

export const pdvAPI = {
  calcularCupom: (itensCarrinho) =>
    request("/caixa/calcular-cupom", {
      method: "POST",
      body: JSON.stringify({ itens_carrinho: itensCarrinho })
    }),

  finalizarVenda: (payload) =>
    request("/caixa/finalizar-venda", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  buscarProdutos: (termo) =>
    request(`/produtos/buscar?q=${encodeURIComponent(termo)}`),

  registrarSuprimento: (payload) =>
    request("/caixa/suprimento", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  registrarSangria: (payload) =>
    request("/caixa/sangria", {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  emitirLeituraX: (terminalId, serie) => {
    const params = new URLSearchParams({ terminal_id: terminalId, serie: serie || "" });
    return request(`/caixa/leitura-x?${params.toString()}`);
  },

  listarNotasReimpressao: (filtro, serie) => {
    const params = new URLSearchParams({ filtro, serie: serie || "" });
    return request(`/caixa/notas-reimpressao?${params.toString()}`);
  },

  obterDetalhesReimpressao: (nfeId) =>
    request(`/caixa/notas/${nfeId}/detalhes-reimpressao`),

  transmitirNotaPendente: (nfeId) =>
    request(`/caixa/notas/${nfeId}/transmitir`, { method: "POST" })
};
