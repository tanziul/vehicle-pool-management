# Task: Implement Dynamic Login Card in home.html

## Objective
Modify the login card in home.html to dynamically switch between login, forgot password, and change password forms within the same card, keeping the logo, eGari text, and overall layout unchanged.

## Steps
1. **Analyze Existing Files**
   - Reviewed home.html (login page)
   - Reviewed registration folder HTML files: password_reset_form.html, password_reset_done.html, password_reset_confirm.html, password_reset_complete.html
   - Reviewed base.html for reference

2. **Plan Modifications**
   - Add hidden divs for forgot password and change password forms inside the login card
   - Modify the "Forgot Password?" link to trigger JavaScript toggle instead of redirect
   - Add JavaScript to handle form switching
   - Ensure forms are styled consistently with the existing login form

3. **Implement Changes**
   - Edit home.html to include all three form states
   - Add CSS classes for hiding/showing forms
   - Add JavaScript for toggling between forms
   - Test the functionality

4. **Testing and Validation**
   - Verify that clicking "Forgot Password?" shows the forgot password form
   - Verify that submitting forgot password shows change password form (simulated flow)
   - Ensure back links return to login form
   - Confirm logo and eGari text remain unchanged

## Files to Edit
- templates/home.html: Main file to modify with dynamic card content

## Dependent Files
- No other files need changes, as we're consolidating the flow into home.html

## Followup Steps
- Test the login functionality
- Ensure forms submit correctly (may need backend adjustments if not handled)
- Verify responsive design
