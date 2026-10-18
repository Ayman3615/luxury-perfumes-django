document.addEventListener("DOMContentLoaded", function () {

    // 1. نظام الدارك مود (Theme Toggle)
    const themeBtn = document.getElementById('theme-btn');
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            let theme = document.documentElement.getAttribute('data-theme');
            let nextTheme = (theme === 'dark') ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', nextTheme);
            localStorage.setItem('theme', nextTheme);
        });
    }

    // 2. القائمة الموحدة (تعمل من زر المزيد السفلي في الموبايل ومن زر الهامبرجر في الكمبيوتر)
    const hamburger = document.getElementById("hamburger") || document.querySelector('.navbar-toggler');
    const moreBtn = document.getElementById("mobileMoreBtn");
    const navLinks = document.getElementById("nav-links") || document.querySelector('.navbar-nav');

    let overlay = document.querySelector(".menu-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.classList.add("menu-overlay");
        document.body.appendChild(overlay);
    }

    function toggleMenu(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (!navLinks) return;

        const isOpen = navLinks.classList.contains("mobile-menu-open") || navLinks.classList.contains("active");
        if (isOpen) {
            closeMenu();
        } else {
            navLinks.classList.add("active", "menu-active", "mobile-menu-open");
            overlay.classList.add("active");
            if (moreBtn) moreBtn.classList.add("active");
        }
    }

    function closeMenu() {
        if (!navLinks) return;
        navLinks.classList.remove("active", "menu-active", "mobile-menu-open");
        overlay.classList.remove("active");
        if (moreBtn) moreBtn.classList.remove("active");
        document.body.style.overflow = "auto";
    }

    if (hamburger) {
        hamburger.onclick = toggleMenu;
    }
    if (moreBtn) {
        moreBtn.onclick = toggleMenu;
    }
    overlay.addEventListener("click", closeMenu);

    document.addEventListener("click", function (event) {
        if (!navLinks) return;
        const isClickInsideMenu = navLinks.contains(event.target);
        const isClickOnHamburger = hamburger && hamburger.contains(event.target);
        const isClickOnMoreBtn = moreBtn && moreBtn.contains(event.target);

        if ((navLinks.classList.contains("active") || navLinks.classList.contains("mobile-menu-open")) &&
            !isClickInsideMenu && !isClickOnHamburger && !isClickOnMoreBtn) {
            closeMenu();
        }
    });

    // 3. الظهور المتدرج الآمن (Scroll Reveal بدون إخفاء دائم للعناصر)
    if ('IntersectionObserver' in window) {
        const observerOptions = { root: null, rootMargin: "0px 0px -5% 0px", threshold: 0.05 };
        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('show-reveal');
                    obs.unobserve(entry.target);
                }
            });
        }, observerOptions);

        const observeElements = () => {
            document.querySelectorAll('.hidden-reveal:not(.show-reveal)').forEach((el) => {
                observer.observe(el);
            });
        };
        observeElements();
    } else {
        document.querySelectorAll('.hidden-reveal').forEach(el => el.classList.add('show-reveal'));
    }

    // 4. تأثير التموج (Ripple Effect)
    document.body.addEventListener('click', function(e) {
        let targetBtn = e.target.closest('.card-btn, .btn-primary, .checkout-btn, .auth-btn, .hero-btn');
        if (targetBtn) {
            if (window.getComputedStyle(targetBtn).position === 'static') {
                targetBtn.style.position = 'relative';
            }
            targetBtn.style.overflow = 'hidden';

            let rect = targetBtn.getBoundingClientRect();
            let x = e.clientX - rect.left;
            let y = e.clientY - rect.top;

            let ripple = document.createElement('span');
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            ripple.classList.add('ripple-effect');

            targetBtn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        }
    });

    // 5. الأيقونات الحية ودعم الترجمة (AJAX السلة والمفضلة مع البوب العائم من تحت)
    document.body.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-add, .heart-btn');
        if (btn && !btn.classList.contains('no-ajax')) {
            e.preventDefault();
            let url = btn.href;
            let isCart = btn.classList.contains('btn-add');
            let originalHtml = btn.innerHTML;

            let isEn = document.documentElement.getAttribute('dir') === 'ltr';
            let loadingText = isEn ? 'Loading...' : 'جاري...';
            let cartMsg = isEn ? 'Added to cart successfully 🛒' : 'تمت إضافة العطر إلى السلة بنجاح! 🛒';
            let favMsg = isEn ? 'Wishlist updated ❤️' : 'تم تحديث قائمة المفضلة ❤️';

            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.7';

            if (isCart) btn.innerHTML = `<span style="font-size: 13px;">${loadingText}</span>`;

            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(() => {
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';

                if (isCart) {
                    btn.innerHTML = originalHtml;
                    let cartCounter = document.getElementById('cart-counter');
                    if (cartCounter) cartCounter.innerText = parseInt(cartCounter.innerText || 0) + 1;
                } else {
                    let svg = btn.querySelector('.heart-svg');
                    if (svg) svg.classList.toggle('active');
                }

                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        html: `<div class="luxury-swal-title">${isCart ? cartMsg : favMsg}</div>`,
                        toast: true,
                        position: 'bottom',
                        showConfirmButton: false,
                        timer: 2800,
                        timerProgressBar: true,
                        customClass: {
                            popup: 'luxury-swal-popup'
                        }
                    });
                }
            })
            .catch(() => window.location.href = url);
        }
    });

    // 6. تحديث السلة اللحظي (Cart AJAX)
    const cartWrapper = document.getElementById('cart-wrapper');
    if (cartWrapper) {
        let isUpdating = false;
        cartWrapper.addEventListener('click', function(e) {
            const btn = e.target.closest('.ajax-cart-action');
            if (btn) {
                e.preventDefault();
                if (isUpdating) return;

                isUpdating = true;
                cartWrapper.style.opacity = '0.5';
                cartWrapper.style.pointerEvents = 'none';

                fetch(btn.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');

                    const newCart = doc.getElementById('cart-wrapper');
                    if (newCart) cartWrapper.innerHTML = newCart.innerHTML;

                    const oldCartCounter = document.getElementById('cart-counter');
                    const newCartCounter = doc.getElementById('cart-counter');
                    if (oldCartCounter && newCartCounter) oldCartCounter.innerHTML = newCartCounter.innerHTML;

                    cartWrapper.style.opacity = '1';
                    cartWrapper.style.pointerEvents = 'auto';
                    isUpdating = false;

                    document.querySelectorAll('#cart-wrapper .hidden-reveal').forEach(el => el.classList.add('show-reveal'));
                })
                .catch(() => window.location.reload());
            }
        });
    }

    // 7. الفلترة اللحظية للمتجر (Shop Filter AJAX)
    const filterForm = document.getElementById('filter-form');
    const gridContainer = document.getElementById('dynamic-product-grid');
    const categoryInput = document.getElementById('category-input');

    if (filterForm && gridContainer) {
        let searchTimeout = null;

        function fetchFilteredData(url) {
            gridContainer.style.opacity = '0.3';
            gridContainer.style.transform = 'translateY(10px)';

            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(response => response.json())
            .then(data => {
                gridContainer.innerHTML = data.html;
                setTimeout(() => {
                    gridContainer.style.opacity = '1';
                    gridContainer.style.transform = 'translateY(0)';
                    bindPaginationEvents();
                }, 50);
            });
        }

        function triggerFilter() {
            const formData = new FormData(filterForm);
            const params = new URLSearchParams(formData);
            fetchFilteredData(`${filterForm.action}?${params.toString()}`);
        }

        document.querySelectorAll('.cat-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                if (categoryInput) categoryInput.value = this.dataset.val;
                triggerFilter();
            });
        });

        filterForm.addEventListener('input', function(e) {
            if (e.target.name === 'q') {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(triggerFilter, 400);
            } else {
                triggerFilter();
            }
        });

        function bindPaginationEvents() {
            document.querySelectorAll('.ajax-page-link').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    fetchFilteredData(this.href);
                    const filterWrap = document.querySelector('.modern-filter-wrapper');
                    if (filterWrap) {
                        window.scrollTo({ top: filterWrap.offsetTop - 20, behavior: 'smooth' });
                    }
                });
            });
        }
        bindPaginationEvents();
    }

    // 8. تفاعلات تقييم النجوم (Star Rating Interaction)
    const stars = document.querySelectorAll('.star-rating-widget span');
    const ratingInput = document.querySelector('select[name="rating"], input[name="rating"]');

    if (stars.length > 0) {
        stars.forEach(star => {
            star.addEventListener('click', function() {
                let val = this.getAttribute('data-val');
                if (ratingInput) ratingInput.value = val;

                stars.forEach(s => {
                    s.classList.remove('selected');
                    s.innerHTML = "☆";
                });

                this.classList.add('selected');

                let current = this;
                while (current) {
                    current.innerHTML = "★";
                    current = current.nextElementSibling;
                }
            });
        });
    }

    // 9. تفاعلات صفحة الدفع والترجمة (Checkout Interactions)
    const checkoutForm = document.getElementById("checkoutForm");
    if (checkoutForm) {
        let isEn = document.documentElement.getAttribute('dir') === 'ltr';

        const paymentMethod = document.getElementById("payment_method");
        const paymentInfo = document.getElementById("payment-info");
        const paymentDetails = document.getElementById("payment-details");
        const proofContainer = document.getElementById("proof-container");
        const proofInput = document.querySelector('input[name="payment_proof"]');

        if (paymentMethod && paymentInfo && paymentDetails) {
            function handlePaymentChange() {
                if (paymentMethod.value === "vodafone") {
                    paymentInfo.style.display = "block";
                    if (proofContainer) proofContainer.style.display = "block";
                    if (proofInput) proofInput.required = true;
                    paymentDetails.innerHTML = isEn
                        ? "Please transfer the amount to <strong>Vodafone Cash</strong>:<br><span style='font-size:18px; color:var(--gold);'>01060660839</span>"
                        : "يرجى تحويل المبلغ إلى <strong>فودافون كاش</strong>:<br><span style='font-size:18px; color:var(--gold);'>01060660839</span>";
                } else if (paymentMethod.value === "instapay_manual") {
                    paymentInfo.style.display = "block";
                    if (proofContainer) proofContainer.style.display = "block";
                    if (proofInput) proofInput.required = true;
                    paymentDetails.innerHTML = isEn
                        ? "Please transfer the amount to <strong>InstaPay</strong>:<br><span style='font-size:18px; color:var(--gold);'>aymanshaban@instapay</span>"
                        : "يرجى تحويل المبلغ إلى <strong>إنستاباي</strong>:<br><span style='font-size:18px; color:var(--gold);'>aymanshaban@instapay</span>";
                } else {
                    paymentInfo.style.display = "none";
                    if (proofContainer) proofContainer.style.display = "none";
                    if (proofInput) proofInput.required = false;
                }
            }
            paymentMethod.addEventListener("change", handlePaymentChange);
            handlePaymentChange();
        }

        const citySelect = document.getElementById("id_city");
        const shippingDisplay = document.getElementById("shipping_cost_display");
        const grandTotalDisplay = document.getElementById("grand_total_display");
        const checkoutData = document.getElementById("checkout-data");

        if (citySelect && shippingDisplay && grandTotalDisplay && checkoutData) {
            let rawTotal = checkoutData.getAttribute("data-cart-total") || "0";
            rawTotal = rawTotal.toString().replace(/,/g, ".").replace(/[^\d.-]/g, "");
            const cartTotal = parseFloat(rawTotal) || 0;

            const shippingRates = {
                qalyubia: 40, cairo: 55, giza: 55, alexandria: 55, sharqia: 55,
                monufia: 55, gharbia: 55, dakahlia: 55, port_said: 55, suez: 55,
                ismailia: 55, damietta: 55, kafr_el_sheikh: 55, beheira: 55,
                fayoum: 75, beni_suef: 75, minya: 75, assiut: 75, sohag: 75,
                qena: 75, luxor: 75, aswan: 75, red_sea: 95, matrouh: 95,
                new_valley: 95, north_sinai: 95, south_sinai: 95,
            };

            let currencyText = isEn ? " EGP" : " ج.م";

            citySelect.addEventListener("change", function () {
                const selectedCity = this.value;
                const shippingCost = Number(shippingRates[selectedCity]) || 0;
                const grandTotal = cartTotal + shippingCost;
                shippingDisplay.innerText = shippingCost + currencyText;
                grandTotalDisplay.innerText = grandTotal.toFixed(2) + currencyText;
            });

            if (citySelect.value) {
                citySelect.dispatchEvent(new Event("change"));
            }
        }

        const phoneInput = document.getElementById('phone_input');
        const phoneError = document.getElementById('phone_error');
        if (phoneInput) {
            phoneInput.addEventListener('input', function() {
                this.value = this.value.replace(/[^0-9]/g, '');
                if (this.value.length === 11 && this.value.match(/^01[0125][0-9]{8}$/)) {
                    this.style.borderColor = '#2ecc71';
                    if (phoneError) phoneError.style.display = 'none';
                } else if (this.value.length > 0) {
                    this.style.borderColor = '#e74c3c';
                    if (phoneError) phoneError.style.display = 'block';
                } else {
                    this.style.borderColor = '';
                    if (phoneError) phoneError.style.display = 'none';
                }
            });
        }

        const addressInput = document.getElementById('address_input');
        const addressError = document.getElementById('address_error');
        const charCount = document.getElementById('char_count');
        if (addressInput) {
            addressInput.addEventListener('input', function() {
                const currentLen = this.value.trim().length;
                if (currentLen >= 20) {
                    if (charCount) { charCount.innerText = `✅ ممتاز! (${currentLen} حرف)`; charCount.style.color = '#2ecc71'; }
                    this.style.borderColor = '#2ecc71';
                    if (addressError) addressError.style.display = 'none';
                } else {
                    if (charCount) { charCount.innerText = `${currentLen} / 20 حرف كحد أدنى`; charCount.style.color = '#e74c3c'; }
                    this.style.borderColor = '#e74c3c';
                    if (currentLen > 0 && currentLen < 20) {
                        if (addressError) addressError.style.display = 'block';
                    } else {
                        if (addressError) addressError.style.display = 'none';
                    }
                }
            });
            if (addressInput.value.length > 0) {
                addressInput.dispatchEvent(new Event('input'));
            }
        }

        const loadingOverlay = document.getElementById("loading-overlay");
        checkoutForm.addEventListener("submit", function (e) {
            let isValid = true;

            if (phoneInput && (phoneInput.value.length !== 11 || !phoneInput.value.match(/^01[0125][0-9]{8}$/))) {
                phoneInput.style.borderColor = '#e74c3c';
                if (phoneError) phoneError.style.display = 'block';
                isValid = false;
            }
            if (addressInput && addressInput.value.trim().length < 20) {
                addressInput.style.borderColor = '#e74c3c';
                if (addressError) addressError.style.display = 'block';
                isValid = false;
            }

            if (!isValid) {
                e.preventDefault();
                return;
            }

            if (loadingOverlay) loadingOverlay.style.display = "flex";
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.style.opacity = "0.5";
                submitBtn.innerText = isEn ? "Processing..." : "جاري المعالجة...";
            }
        });
    }

    // 10. تظبيط حقول جانجو أوتوماتيكياً (لصفحة التسجيل)
    const authInputs = document.querySelectorAll('.auth-card input');
    authInputs.forEach(input => {
        if (input.type !== 'submit' && input.type !== 'hidden') {
            input.classList.add('premium-input');
            input.style.width = '100%';
        }
        if (input.type === 'password') {
            input.style.paddingLeft = '45px';
            if (input.name.includes('password') && !input.name.includes('confirm')) {
                const strengthContainer = document.createElement('div');
                strengthContainer.className = 'password-strength-bar';
                const strengthFill = document.createElement('div');
                strengthFill.className = 'password-strength-fill';
                strengthContainer.appendChild(strengthFill);
                input.parentElement.appendChild(strengthContainer);

                input.addEventListener('input', function() {
                    let val = input.value;
                    let strength = 0;
                    if (val.length >= 6) strength += 25;
                    if (val.match(/[a-zA-Z]+/)) strength += 25;
                    if (val.match(/[0-9]+/)) strength += 25;
                    if (val.match(/[$@#&!%^*?_]+/)) strength += 25;
                    if (strength > 100) strength = 100;
                    strengthFill.style.width = strength + '%';

                    if (strength <= 25) strengthFill.style.backgroundColor = '#e74c3c';
                    else if (strength <= 75) strengthFill.style.backgroundColor = '#f39c12';
                    else strengthFill.style.backgroundColor = '#2ecc71';
                });
            }
        }
    });

    // 11. تهيئة مسارات صور السلايدر وتحديث الحجم الافتراضي
    window.productMediaList = [];
    window.currentMediaIndex = 0;
    document.querySelectorAll('.thumb-box').forEach(function(thumb) {
        window.productMediaList.push(thumb.getAttribute('data-url'));
    });

    const defaultCheckedSize = document.querySelector('.size-option input[type="radio"]:checked');
    if (defaultCheckedSize) {
        setTimeout(() => {
            if (typeof window.updateSelection === "function") {
                window.updateSelection(defaultCheckedSize);
            }
        }, 50);
    }
});

// ==========================================
// دوال عامة (خارج DOMContentLoaded)
// ==========================================

function filterGrid() {
    let searchInput = document.getElementById('productSearch');
    if (!searchInput) return;

    let input = searchInput.value.toLowerCase();
    let cards = document.getElementsByClassName('dashboard-card');

    for (let i = 0; i < cards.length; i++) {
        let title = cards[i].querySelector('.dashboard-product-title').innerText.toLowerCase();
        cards[i].style.display = title.includes(input) ? "flex" : "none";
    }
}

const colorDictionary = {
    'خشب': '#8b4513', 'عود': '#5c4033', 'صندل': '#d2b48c', 'أرز': '#a0522d',
    'ليمون': '#f1c40f', 'برتقال': '#e67e22', 'حمضيات': '#f39c12', 'برغموت': '#f39c12',
    'فانيليا': '#f5deb3', 'عنبر': '#d35400', 'مسك': '#ffebcd', 'تونكا': '#8b4513',
    'ورد': '#ff69b4', 'ياسمين': '#fffacd', 'لافندر': '#9b59b6', 'أزهار': '#ffb6c1',
    'نعناع': '#2ecc71', 'باتشولي': '#27ae60', 'عشب': '#7cfc00', 'منعش': '#2ecc71',
    'توابل': '#c0392b', 'قرفة': '#d2691e', 'هيل': '#8b4513', 'فلفل': '#696969',
    'ماء': '#3498db', 'بحر': '#2980b9', 'أكوا': '#00bfff',
    'جلد': '#8b4513', 'تبغ': '#cd853f', 'أروماتك': '#8e44ad'
};

function autoPredictColor(inputElem) {
    let text = inputElem.value.toLowerCase();
    let colorPicker = inputElem.parentElement.querySelector('input[type="color"]');

    for (const [keyword, hex] of Object.entries(colorDictionary)) {
        if (text.includes(keyword)) {
            if (colorPicker) colorPicker.value = hex;
            break;
        }
    }
}

function addAccordRow() {
    const container = document.getElementById('accords-container');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'accord-row';
    row.style.cssText = 'display: flex; gap: 10px; align-items: center; background: #111; padding: 15px; border-radius: 8px; border: 1px solid #444; animation: fadeIn 0.3s ease; flex-wrap: wrap;';

    let isEn = document.documentElement.getAttribute('dir') === 'ltr';
    let namePlaceholder = isEn ? "Note Name (AR)" : "اسم النوتة بالعربي (مثل: عود)";
    let nameEnPlaceholder = isEn ? "Note Name (EN - Optional)" : "الاسم بالإنجليزي (اختياري)";
    let percentagePlaceholder = isEn ? "Percentage %" : "النسبة %";
    let colorTitle = isEn ? "Choose Color" : "اختر اللون";

    row.innerHTML = `
        <input type="text" name="accord_name" placeholder="${namePlaceholder}" required onkeyup="autoPredictColor(this)" style="flex: 2; min-width: 140px; padding: 10px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: white;">
        <input type="text" name="accord_name_en" placeholder="${nameEnPlaceholder}" style="flex: 2; min-width: 140px; padding: 10px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: white;">
        <input type="number" name="accord_percentage" placeholder="${percentagePlaceholder}" required min="10" max="100" style="flex: 1; min-width: 90px; padding: 10px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: white;">
        <input type="color" name="accord_color" value="#d4af37" required style="width: 50px; height: 44px; background: transparent; border: none; cursor: pointer; padding: 0;" title="${colorTitle}">
        <button type="button" onclick="this.parentElement.remove()" style="background: #e74c3c; color: white; border: none; border-radius: 6px; padding: 10px 15px; cursor: pointer; font-weight: bold;">X</button>
    `;
    container.appendChild(row);
}

window.togglePassword = function(iconSpan) {
    const input = iconSpan.parentElement.querySelector('input');

    iconSpan.style.transform = "translateY(-50%) scale(0.8)";
    setTimeout(() => iconSpan.style.transform = "translateY(-50%) scale(1)", 150);

    if (input.type === "password") {
        input.type = "text";
        iconSpan.innerHTML = `
            <svg class="eye-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                <line x1="1" y1="1" x2="23" y2="23"></line>
            </svg>`;
    } else {
        input.type = "password";
        iconSpan.innerHTML = `
            <svg class="eye-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>`;
    }
};

window.updateSelection = function(radioBtn) {
    let newPrice = radioBtn.getAttribute('data-price');
    let priceDiv = document.getElementById('display-price') || document.getElementById('dynamic-price');
    let isEn = document.documentElement.getAttribute('dir') === 'ltr';
    let currencyText = isEn ? " EGP" : " ج.م";

    if (priceDiv && newPrice) {
        priceDiv.innerText = newPrice + currencyText;
        priceDiv.style.transition = "all 0.2s ease";
        priceDiv.style.transform = "scale(1.12)";
        priceDiv.style.color = "#b8962e";
        setTimeout(() => {
            priceDiv.style.transform = "scale(1)";
            priceDiv.style.color = "var(--gold)";
        }, 200);
    }

    let targetImageUrl = radioBtn.getAttribute('data-image');
    if (window.productMediaList && targetImageUrl) {
        let mediaIndex = window.productMediaList.indexOf(targetImageUrl);
        if (mediaIndex !== -1) {
            window.changeMedia(mediaIndex);
        }
    }

    let size = radioBtn.getAttribute('data-size') || radioBtn.value;
    let addBtn = document.getElementById('add-to-cart-btn');
    let buyBtn = document.getElementById('buy-now-btn');

    if (addBtn && size) {
        let url = new URL(addBtn.href, window.location.origin);
        url.searchParams.set('size', size);
        addBtn.href = url.toString();
    }
    if (buyBtn && size) {
        let url = new URL(buyBtn.href, window.location.origin);
        url.searchParams.set('size', size);
        buyBtn.href = url.toString();
    }
};

window.changeMedia = function(index) {
    if (!window.productMediaList || index < 0 || index >= window.productMediaList.length) return;
    window.currentMediaIndex = index;

    const mainMediaElem = document.getElementById("main-product-media");
    if (!mainMediaElem) return;

    document.querySelectorAll('.thumb-box').forEach(th => th.classList.remove('active'));
    let activeThumb = document.querySelector(`.thumb-box[data-url="${window.productMediaList[index]}"]`);
    if (activeThumb) activeThumb.classList.add('active');

    mainMediaElem.classList.add("fade-out");

    setTimeout(() => {
        let url = window.productMediaList[window.currentMediaIndex];

        if (url.endsWith('.mp4') || url.endsWith('.webm')) {
            mainMediaElem.outerHTML = `<video id="main-product-media" controls autoplay muted style="max-width: 100%; max-height: 100%; object-fit: contain;"><source src="${url}" type="video/mp4"></video>`;
        } else {
            if (mainMediaElem.tagName === 'VIDEO') {
                mainMediaElem.outerHTML = `<img id="main-product-media" src="${url}" class="fade-out" style="max-width: 100%; max-height: 100%; object-fit: contain;">`;
            } else {
                mainMediaElem.src = url;
            }
        }

        setTimeout(() => {
            let newElem = document.getElementById("main-product-media");
            if (newElem) newElem.classList.remove("fade-out");
        }, 50);
    }, 200);
};

window.nextMedia = function() {
    if (!window.productMediaList || window.productMediaList.length <= 1) return;
    let newIndex = (window.currentMediaIndex + 1) % window.productMediaList.length;
    window.changeMedia(newIndex);
};

window.prevMedia = function() {
    if (!window.productMediaList || window.productMediaList.length <= 1) return;
    let newIndex = (window.currentMediaIndex - 1 + window.productMediaList.length) % window.productMediaList.length;
    window.changeMedia(newIndex);
};

window.syncThumbnail = function(element) {
    let url = element.getAttribute('data-url');
    if (window.productMediaList) {
        let index = window.productMediaList.indexOf(url);
        if (index !== -1) {
            window.changeMedia(index);
        }
    }
};