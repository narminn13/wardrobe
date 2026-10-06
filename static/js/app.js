document.addEventListener("DOMContentLoaded", function () {
    const imageInput = document.querySelector(
        'input[type="file"][multiple]'
    );

    const preview = document.getElementById(
        "uploadPreview"
    );

    const form = document.getElementById(
        "uploadForm"
    );

    const button = document.getElementById(
        "uploadButton"
    );

    if (imageInput && preview) {
        imageInput.addEventListener(
            "change",
            function () {
                preview.innerHTML = "";

                const files = Array.from(
                    imageInput.files
                );

                files.forEach(function (file) {
                    if (
                        !file.type.startsWith(
                            "image/"
                        )
                    ) {
                        return;
                    }

                    const reader =
                        new FileReader();

                    reader.onload = function (event) {
                        const column =
                            document.createElement(
                                "div"
                            );

                        column.className =
                            "col-6 col-md-3";

                        column.innerHTML = `
                            <div class="card border-0 shadow-sm">
                                <img
                                    src="${event.target.result}"
                                    class="card-img-top"
                                    style="height: 180px; object-fit: cover;"
                                >
                                <div class="card-body p-2">
                                    <small>
                                        ${file.name}
                                    </small>
                                </div>
                            </div>
                        `;

                        preview.appendChild(
                            column
                        );
                    };

                    reader.readAsDataURL(
                        file
                    );
                });
            }
        );
    }

    if (form && button) {
        form.addEventListener(
            "submit",
            function () {
                button.disabled = true;

                button.innerHTML = `
                    <span
                        class="spinner-border spinner-border-sm me-2"
                    ></span>
                    AI is analyzing your clothes...
                `;
            }
        );
    }
});