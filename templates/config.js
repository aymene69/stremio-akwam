const sorts = ['quality', 'seedsdesc', 'sizedesc', 'sizeasc', 'qualitythensize'];
const qualityExclusions = ['4k', '1080p', '720p', '480p', 'rips', 'cam', 'unknown'];
const languages = ['en', 'fr', 'es', 'de', 'it', 'pt', 'ru', 'in', 'nl', 'hu', 'la', 'multi'];

function setElementDisplay(elementId, displayStatus) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.style.display = displayStatus;
}


function getLink(method) {
    const tmdbApi = document.getElementById('tmdb-api-key').value;
    const encodedTmdbApi = btoa(tmdbApi);
    const currentUrl = window.location.href;
    const baseUrl = currentUrl.split('/configure')[0];
    const link = `${baseUrl}/${encodedTmdbApi}/manifest.json`;
    let cleanedLink = link.replace(/^https?:\/\//, '');
    console.log(cleanedLink);
    if (method === 'link') {
        window.open(`stremio://${cleanedLink.replace("//", "/")}`, "_blank");
    } else if (method === 'copy') {
        if (!navigator.clipboard) {
            alert('Your browser does not support clipboard');
            console.log(link);
            return;
        }

        navigator.clipboard.writeText(link).then(() => {
            alert('Link copied to clipboard');
        }, () => {
            alert('Error copying link to clipboard');
        });
    }
}

