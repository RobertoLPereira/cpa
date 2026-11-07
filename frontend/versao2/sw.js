const CACHE_NAME = "pdv-fiscal-v4";
// Adicionamos o icon.png na lista de recursos locais que o navegador vai guardar em cache
const ASSETS_TO_CACHE = [
    "index.html",
    "app.js",
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
