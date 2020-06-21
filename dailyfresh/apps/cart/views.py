from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.maxin import LoginRequiredMixin
class CartAddView(View):
    '''购物车记录添加'''
    def post(self,request):
        #用户校验
        user=request.user
        if not user.is_authenticated:
            #用户未登录
            return JsonResponse({'res':0,'errmsg':'请先登录'})
        #接收数据
        sku_id=request.POST.get('sku_id')
        count=request.POST.get('count')
        #数据校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据不完整'})
        #校验添加的商品数量
        try:
            count=int(count)
        except Exception as e:
            return JsonResponse({'res':2,'errmsg':'商品数目出错'})
        #校验商品是否存在
        try:
            sku=GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            #商品不存在
            return JsonResponse({'res':3,'errmsg':'商品不存在'})
        #业务处理：添加购物车记录
        conn=get_redis_connection('default')
        cart_key='cart_%d'%user.id
        #返回应答
        cart_count=conn.hget(cart_key,sku_id)
        if cart_count:
            count+=int(cart_count)
        #校验商品库存
        if count>sku.stock:
            return JsonResponse({'res':4,'errmsg':'商品库存不足'})
        #设置hash中sku_id对应的值
        #hset->如果sku_id已经存在，更新数据，如果sku_id不存在，添加数据
        conn.hset(cart_key,sku_id,count)
        #计算机用户购物车中商品的条目数
        total_count=conn.hlen(cart_key)
        return JsonResponse({'res':5,'total_count':total_count,'message':'添加成功'})

#/cart/
class CartInfoView(LoginRequiredMixin,View):
    def get(self,request):
        #获取登录的用户
        user=request.user
        #获取用户购物车中商品的信息
        conn=get_redis_connection('default')
        cart_key='cart_%d'%user.id
        cart_dict=conn.hgetall(cart_key)
        skus=[]
        total_count=0#保存用户购物车中商品的总数目和总价格
        total_price=0
        for sku_id,count in cart_dict.items():
            sku=GoodsSKU.objects.get(id=sku_id)#根据商品的id获取商品的信息
            amount=sku.price*int(count)#计算商品的小计
            sku.amount=amount#动态给sku添加一个属性amount，保存商品的小计
            sku.count=count#动态的给sku添加一个属性count，保存购物车中对应商品的数量
            skus.append(sku)#添加
            total_count+=int(count)#计算商品总数目
            total_price+=amount#计算商品总价格
            #组织上下文
            context={'total_count':total_count,
                     'total_price':total_price,
                     'skus':skus}
        return render(request,'cart.html',context)

#更新购物车记录
#采用ajax post请求
#前端需要传递的参数：商品id(sku_id)更新的商品数量（count）
class CartUpdateView(View):#/cart/update
    '''购物车记录更新'''
    def post(self,request):
        '''购物车记录更新'''
        # 用户校验
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        #业务处理：更新购物车记录
        conn=get_redis_connection('default')
        cart_key='cart_%d'%user.id
        #校验商品的库存
        if count>sku.stock:
            return JsonResponse({'res':4,'errmsg':'商品库存不足'})
        #更新
        conn.hset(cart_key,sku_id,count)
        #计算用户购物车中商品的总件数
        total_count=0
        vals=conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        #返回应答
        return JsonResponse({'res':5,'total_count':total_count,'message':'更新成功'})

#删除购物车请求
#采用ajax post请求
#前端需要传递的参数：商品id(sku_id)
#/cart/delete
class CartDeleteView(View):
    '''购物车记录删除'''
    def post(self,request):
        # 用户校验
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        #接收参数
        sku_id=request.POST.get('sku_id')
        #数据的校验
        if not sku_id:
            return JsonResponse({'res':1,'errmsg':'无效的商品id'})
        #校验商品是否存在
        try:
            sku=GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':2,'errmsg':'商品不存在'})
        #业务处理：删除购物车记录
        conn=get_redis_connection('default')
        cart_key='cart_%d'%user.id
        #删除hdel
        conn.hdel(cart_key,sku_id)
        #计算用户购物车中商品的总件数
        total_count=0
        vals=conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        #返回应答
        return JsonResponse({'res':3,'total_count':total_count,'message':'删除成功'})