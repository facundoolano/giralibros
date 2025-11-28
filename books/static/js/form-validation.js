/**
 * Generic form validation that disables submit buttons when required fields are empty.
 * Works with any form that has required inputs and a submit button.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Find all forms with required fields
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        const requiredInputs = form.querySelectorAll('input[required], textarea[required], select[required]');
        const submitButton = form.querySelector('button[type="submit"]');

        // Only process forms that have both required fields and a submit button
        if (requiredInputs.length === 0 || !submitButton) {
            return;
        }

        const checkFormValidity = () => {
            const allFilled = Array.from(requiredInputs).every(input => {
                return input.value.trim() !== '';
            });

            if (allFilled) {
                submitButton.disabled = false;
                submitButton.classList.remove('is-light');
                submitButton.classList.add('is-primary');
            } else {
                submitButton.disabled = true;
                submitButton.classList.remove('is-primary');
                submitButton.classList.add('is-light');
            }
        };

        // Check validity on input
        requiredInputs.forEach(input => {
            input.addEventListener('input', checkFormValidity);
        });

        // Initial check
        checkFormValidity();
    });
});
