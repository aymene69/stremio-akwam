function getLink(method) {
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split('/configure')[0];
    const link = `${baseUrl}/manifest.json`;
    let cleanedLink = link.replace(/^https?:\/\//, '');
    
    console.log('Manifest link:', link);
    
    if (method === 'link') {
        // Ouvrir directement dans Stremio
        window.open(`stremio://${cleanedLink.replace("//", "/")}`, "_blank");
    } else if (method === 'copy') {
        // Copier le lien dans le presse-papier
        if (!navigator.clipboard) {
            alert('Votre navigateur ne supporte pas le presse-papier');
            console.log(link);
            return;
        }

        navigator.clipboard.writeText(link).then(() => {
            alert('Lien copié dans le presse-papier !');
        }, () => {
            alert('Erreur lors de la copie du lien');
        });
    }
}

