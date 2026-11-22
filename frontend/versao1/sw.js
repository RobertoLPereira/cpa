const CACHE_NAME = "pdv-modular-v1";
// Adicionamos o icon.png na lista de recursos locais que o navegador vai guardar em cache
const ASSETS_TO_CACHE = [
    "./",
    "./index.html",
    "./auth_retaguarda.js",
    "./nfe_400.jpg",
    "../css/temas.css",
    "../css/base.css",
    "../css/layout.css",
    "../css/modais.css",
    "../js/main.js",
    "../js/state.js",
    "../js/api.js",
    "../js/ui/bobina.js",
    "../js/ui/modal-universal.js",
    "../js/ui/modal-busca.js",
    "../js/ui/modal-pagamento.js",
    "../js/ui/modal-reimp.js",
    "../js/operacoes/venda.js",
    "../js/operacoes/gaveta.js",
    "manifest.json",
    "icone.svg"
];

// Instalação do PWA: Armazena a interface de forma estável
self.addEventListener("install", (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log("[PWA Cache] Armazenando interface local para contingência.");
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

// Ativação do PWA: Limpa caches antigos do terminal automaticamente
self.addEventListener("activate", (e) => {
    e.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
});

// Interceptação de Requisições: Serve os arquivos visuais locais instantaneamente
self.addEventListener("fetch", (e) => {
    // Permite que chamadas para a API local passem direto sem validação de cache
    if (e.request.url.includes("/api/v1/")) {
        return;
    }
    
    e.respondWith(
        caches.match(e.request).then((cachedResponse) => {
            return cachedResponse || fetch(e.request);
        })
    );
});
