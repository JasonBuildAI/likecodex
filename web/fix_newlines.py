path = r'd:\App\AgentProjects\likecodex\likecodex\web\src\app\page.tsx'
with open(path, 'rb') as f:
    data = f.read()
text = data.decode('utf-8')

# Fix: replace literal \r\n sequences embedded in string conditions  
old1 = "beforeCursor[atIndex - 1] === ' \r\n'"
new1 = "beforeCursor[atIndex - 1] === '\\\\n'"
text = text.replace(old1, new1)

old2 = "query.includes(' \r\n')"
new2 = "query.includes('\\\\\\\\n')"
text = text.replace(old2, new2)

with open(path, 'wb') as f:
    f.write(text.encode('utf-8'))
print('Fixed')
