// main.js — students will add JavaScript here as features are built

// Ask for confirmation before submitting any form marked with data-confirm.
// Delegated, so it works for every such form without per-page setup. With JS
// disabled the form simply submits.
document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form.hasAttribute || !form.hasAttribute('data-confirm')) return;
    if (!window.confirm(form.getAttribute('data-confirm'))) {
        event.preventDefault();
    }
});
