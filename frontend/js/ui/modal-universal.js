// ==========================================================================
// UI/MODAL-UNIVERSAL.JS - Caixa de entrada modal (moeda, qtde, CPF, senha)
// ==========================================================================
import { estadoPDV } from "../state.js";
import { focarEAN } from "./bobina.js";

let resolverAtual = null;
let mascaraAtual = "texto";

export function pedirDadoModal({ titulo, label, valorInicial = "", tipo = "texto", dica = "" }) {
  return new Promise((resolve) => {
    resolverAtual = resolve;
    mascaraAtual = tipo;
    estadoPDV.modalAtivo = "UNIVERSAL";

    document.getElementById("modal-univ-titulo").innerText = titulo;
    document.getElementById("modal-univ-label").innerText = label;
    document.getElementById("modal-univ-dica").innerText = dica;

    const inp = document.getElementById("modal-univ-campo");
    inp.type = tipo === "senha" ? "password" : "text";
    inp.style.textAlign = ["moeda", "qtde", "percentual"].includes(tipo) ? "right" : "center";
    inp.value = valorInicial;

    document.getElementById("modal-input-universal").classList.remove("hidden");
    inp.focus();
    inp.select();
  });
}

export function fecharModalUniversal(valorRetorno) {
  document.getElementById("modal-input-universal").classList.add("hidden");
  estadoPDV.modalAtivo = null;
  const resolve = resolverAtual;
  resolverAtual = null;
  if (resolve) resolve(valorRetorno);
  focarEAN();
}

export function inicializarModalUniversal() {
  const inp = document.getElementById("modal-univ-campo");

  inp.addEventListener("input", function () {
    if (mascaraAtual === "moeda" || mascaraAtual === "percentual") {
      const digits = this.value.replace(/\D/g, "") || "0";
      this.value = (parseInt(digits, 10) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (mascaraAtual === "qtde") {
      const digits = this.value.replace(/\D/g, "") || "0";
      this.value = (parseInt(digits, 10) / 1000).toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    } else if (mascaraAtual === "cpfcnpj") {
      let v = this.value.replace(/\D/g, "").slice(0, 14);
      v = v.length <= 11
        ? v.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2")
        : v.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
      this.value = v;
    } else if (mascaraAtual === "inteiro") {
      this.value = this.value.replace(/\D/g, "");
    }
  });

  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); fecharModalUniversal(inp.value); }
    if (e.key === "Escape") { e.preventDefault(); fecharModalUniversal(null); }
  });
}
