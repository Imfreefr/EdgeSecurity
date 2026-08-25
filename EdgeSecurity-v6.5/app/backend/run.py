import os

import uvicorn


if __name__ == '__main__':
    uvicorn.run(
        'app:app',
        host=os.getenv('EDGE_API_HOST', '0.0.0.0'),
        port=int(os.getenv('EDGE_API_PORT', '8000')),
        reload=False,
    )
