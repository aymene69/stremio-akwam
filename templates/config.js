function getLink(method) {
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split('/configure')[0];
    const link = `${baseUrl}/manifest.json`;
    let cleanedLink = link.replace(/^https?:\/\//, '');
    
    console.log('Manifest link:', link);
    
    if (method === 'link') {
        // Open directly in Stremio
        window.open(`stremio://${cleanedLink.replace("//", "/")}`, "_blank");
    } else if (method === 'copy') {
        // Copy link to clipboard
        if (!navigator.clipboard) {
            alert('Your browser does not support clipboard');
            console.log(link);
            return;
        }

        navigator.clipboard.writeText(link).then(() => {
            alert('Link copied to clipboard!');
        }, () => {
            alert('Error copying link to clipboard');
        });
    }
}

