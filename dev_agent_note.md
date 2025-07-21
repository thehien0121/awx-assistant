# Prompt Chuẩn Tạo Function Tools AWX
**Yêu cầu:** Tạo function tools cho các endpoint thuộc nhóm Roles

**Workflow thực hiện:**
# BẮT BUỘC SỬ DỤNG PLAYWIRGHT ĐỂ MỞ TÀI LIỆU API
https://ansible.readthedocs.io/projects/awx/en/latest/rest_api/api_ref.html
1. **Click vào tên endpoint** - Click vào link endpoint cụ thể (ví dụ: GET /api/, POST /api/v2/authtoken/)
2. **Đọc nội dung endpoint** - Xem chi tiết:
   - URL endpoint
   - Request type (GET, POST, PUT, DELETE, PATCH)
   - Parameters (query params, body params)
   - Response format và status codes
   - Headers required
3. **Tạo function tool** - Xây dựng function theo cấu trúc tương tự các function có sẵn trong `agent_tools/awx_mcp.py`:
   - Sử dụng decorator `@function_tool`
   - Định nghĩa parameters phù hợp với API
   - Sử dụng hàm `make_request()` đã có
   - Thêm docstring mô tả chức năng
   - Xử lý response phù hợp

**Ví dụ prompt cụ thể:**

```
Tôi muốn tạo function tools cho các endpoint thuộc nhóm Roles. Hãy:

1. Click vào endpoint "GET /api/" 
2. Đọc nội dung chi tiết về URL, request type, parameters, response
3. Tạo function tool tương ứng theo cấu trúc trong file awx_mcp.py

Sau đó tiếp tục với endpoint tiếp theo trong nhóm Roles.
```

**Lưu ý:**
- Chỉ tạo function cho các endpoint có ý nghĩa thực tế (bỏ qua các endpoint test/demo)
- Đảm bảo function có tên mô tả rõ chức năng
- Xử lý lỗi và validation phù hợp
- Tuân thủ cấu trúc code hiện có trong file
