/* =========================================================
   RUBIX CLUB
   GLOBAL JAVASCRIPT
========================================================= */


document.addEventListener(
    "DOMContentLoaded",
    function () {


        /* ==============================================
           MOBILE MENU
        ============================================== */

        const menuButton =
            document.getElementById(
                "mobileMenuButton"
            );


        const mobileMenu =
            document.getElementById(
                "mobileMenu"
            );


        if (menuButton && mobileMenu) {

            menuButton.addEventListener(
                "click",
                function () {

                    mobileMenu.classList.toggle(
                        "active"
                    );

                }
            );

        }



        /* ==============================================
           FLASH MESSAGE AUTO HIDE
        ============================================== */

        const flash =
            document.querySelector(
                ".flash-container"
            );


        if (flash) {

            setTimeout(
                function () {

                    flash.style.opacity = "0";

                    flash.style.transform =
                        "translateY(-10px)";

                    flash.style.transition =
                        "0.4s ease";


                    setTimeout(
                        function () {

                            flash.remove();

                        },
                        400
                    );

                },
                4000
            );

        }



        /* ==============================================
           CLOSE MOBILE MENU AFTER CLICK
        ============================================== */

        const mobileLinks =
            document.querySelectorAll(
                ".mobile-menu a"
            );


        mobileLinks.forEach(
            function (link) {

                link.addEventListener(
                    "click",
                    function () {

                        if (mobileMenu) {

                            mobileMenu.classList.remove(
                                "active"
                            );

                        }

                    }
                );

            }
        );


    }
);